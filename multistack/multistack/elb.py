import os
import json
from aws_cdk import (
    aws_ec2 as ec2,
    aws_autoscaling as asg,
    aws_elasticloadbalancingv2 as elb,
    aws_elasticloadbalancingv2_targets as lbtargets,
    aws_cloudwatch as cw,
    aws_certificatemanager as acm,
    aws_route53 as r53,
    aws_route53_targets as r53tgs,
    core,
)
account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"])
region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])
resconf = "resourcesmap.cfg"
with open(resconf) as resfile:
    resmap = json.load(resfile)
with open('zonemap.cfg') as zonefile:
    zonemap = json.load(zonefile)
class alb(core.Stack):
    def __init__(self, scope: core.Construct, construct_id: str, res, preflst, allowall, vpc = ec2.Vpc, allowsg = ec2.SecurityGroup, tgrt = asg.AutoScalingGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # get imported objects
        self.vpc = vpc
        allowsg = allowsg
        tgrt = tgrt
        # get config for resource
        res = res
        appname = resmap['Mappings']['Resources'][res]['NAME']
        appdomain = resmap['Mappings']['Resources'][res]['DOMAIN']
        albface = resmap['Mappings']['Resources'][res]['INTERNET']
        ressubgrp = resmap['Mappings']['Resources'][res]['SUBNETGRP']
        # create security group for LB
        self.lbsg = ec2.SecurityGroup(
            self,
            f"{construct_id}:MyLBsg",
            allow_all_outbound=True,
            vpc=self.vpc
        )
        #create alb
        if albface == 'True':
            if self.vpc.stack == 'Ipv6':
                lbstack = elb.IpAddressType.DUAL_STACK
            else:
                lbstack = elb.IpAddressType.IPV4
        self.alb = elb.ApplicationLoadBalancer(
            self,
            f"{construct_id}:myALB",
            vpc=self.vpc,
            internet_facing=True,
            ip_address_type=(lbstack),
            vpc_subnets=ec2.SubnetSelection(subnet_group_name=ressubgrp,one_per_az=True),
            security_group=self.lbsg
        )
        core.CfnOutput(
            self,
            f"{construct_id}:ALB DNS",
            value=self.alb.load_balancer_dns_name
        )
        # get hosted zone id
        self.hz = r53.HostedZone.from_lookup(
            self,
            f"{construct_id}:Domain",
            domain_name=appdomain,
            private_zone=False
        )
        r53.ARecord(
            self,
            f"{construct_id}:fqdn",
            zone=self.hz,
            record_name=f"{appname}.{appdomain}",
            target=r53.RecordTarget.from_alias(r53tgs.LoadBalancerTarget(self.alb))
        )
        # generate public certificate
        self.cert = acm.Certificate(
            self,
            f"{construct_id}:Certificate",
            domain_name=f"{appname}.{appdomain}",
            validation=acm.CertificateValidation.from_dns(self.hz)
        )
        # configure listener
        self.elblistnrs = self.alb.add_listener(
            f"{construct_id}:Listener_https",
            port=443,
            protocol=elb.ApplicationProtocol.HTTPS,
            certificate_arns=[self.cert.certificate_arn]
        )
        #redir http traffic to https
        self.alb.add_redirect(
            source_port=80,
            source_protocol=elb.ApplicationProtocol.HTTP,
            target_port=443,
            target_protocol=elb.ApplicationProtocol.HTTPS
        )
        # allow ingress access 
        if allowall == True:
            self.elblistnrs.connections.allow_default_port_from(
            other=ec2.Peer.any_ipv4(),
            description="Allow from anyone on LB port"
            )
            if self.vpc.stack == 'Ipv6':
                self.elblistnrs.connections.allow_default_port_from(
                    other=ec2.Peer.any_ipv6(),
                    description="Allow from anyone on LB port"
                )
        if preflst == True:
            # get prefix list from file to allow traffic from the office
            srcprefix = zonemap['Mappings']['RegionMap'][region]['PREFIXLIST']        
            self.elblistnrs.connections.allow_default_port_from(
                other=ec2.Peer.prefix_list(srcprefix),
                description="Allow from prefix list on LB port"
            )
        # allow egress access to target
        self.tgrp = self.elblistnrs.add_targets(
            f"{construct_id}:My Default Fleet",
            port=80,
            targets=[tgrt]
        )
        # create alarm for UnHealthyHostCount
        self.alarmtargrunhealth = self.tgrp.metric("UnHealthyHostCount")
        cw.Alarm(
            self,
            f"{construct_id}:UnHealthyHostCount",
            metric=self.alarmtargrunhealth,
            evaluation_periods=1,
            threshold=0,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
