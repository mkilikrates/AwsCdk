import os
import json
from aws_cdk import (
    aws_ec2 as ec2,
    aws_autoscaling as asg,
    aws_cloudwatch as cw,
    core,
)
account = core.Aws.ACCOUNT_ID
region = core.Aws.REGION
resconf = "resourcesmap.cfg"
with open(resconf) as resfile:
    resmap = json.load(resfile)
with open('zonemap.cfg') as zonefile:
    zonemap = json.load(zonefile)

class main(core.Stack):
    def __init__(self, scope: core.Construct, construct_id: str, res, preflst, allowall, vpc = ec2.Vpc, allowsg = ec2.SecurityGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # get imported objects
        self.vpc = vpc
        if allowsg != '':
            self.allowsg = allowsg
        # get config for resource
        res = res
        ressubgrp = resmap['Mappings']['Resources'][res]['SUBNETGRP']
        ressize = resmap['Mappings']['Resources'][res]['SIZE']
        resclass = resmap['Mappings']['Resources'][res]['CLASS']
        mykey = resmap['Mappings']['Resources'][res]['KEY']
        usrdatafile = resmap['Mappings']['Resources'][res]['USRFILE']
        mincap = resmap['Mappings']['Resources'][res]['min']
        maxcap = resmap['Mappings']['Resources'][res]['max']
        desircap = resmap['Mappings']['Resources'][res]['desir']
        resmon = resmap['Mappings']['Resources'][res]['MONITOR']
        usrdata = open(usrdatafile, "r").read()
        # create security group for Auto Scale Group
        self.asgsg = ec2.SecurityGroup(
            self,
            f"{construct_id}:MyASGsg",
            allow_all_outbound=True,
            vpc=self.vpc
        )
        # add egress rule
        if self.vpc.stack == 'Ipv6':
            ec2.CfnSecurityGroupEgress(
                self,
                f"{construct_id}:ASGEgressAllIpv6",
                ip_protocol="-1",
                cidr_ipv6="::/0",
                group_id=self.asgsg.security_group_id
            )
        else:
            ec2.CfnSecurityGroupEgress(
                self,
                f"{construct_id}:ASGEgressAllIpv4",
                ip_protocol="-1",
                cidr_ip="0.0.0.0/0",
                group_id=self.asgsg.security_group_id
            )
        # add ingress rule
        if allowsg != '':
            self.asgsg.add_ingress_rule(
                self.allowsg,
                ec2.Port.all_traffic()
            )
        if preflst == True:
            # get prefix list from file to allow traffic from the office
            mymap = core.CfnMapping(
                self,
                f"{construct_id}Map",
                mapping=zonemap["Mappings"]["RegionMap"]
            )
            srcprefix = mymap.find_in_map(core.Aws.REGION, 'PREFIXLIST')
            self.asgsg.add_ingress_rule(
                ec2.Peer.prefix_list(srcprefix),
                ec2.Port.all_traffic()
            )
        if allowall == True:
            self.asgsg.add_ingress_rule(
                ec2.Peer.any_ipv4,
                ec2.Port.all_traffic()
            )
            self.asgsg.add_ingress_rule(
                ec2.Peer.any_ipv6,
                ec2.Port.all_traffic()
            )
        if type(allowall) == int or type(allowall) == float:
            self.asgsg.add_ingress_rule(
                ec2.Peer.any_ipv4(),
                ec2.Port.tcp(allowall)
            )
            self.asgsg.add_ingress_rule(
                ec2.Peer.any_ipv6(),
                ec2.Port.tcp(allowall)
            )
        # create Auto Scalling Group
        self.asg = asg.AutoScalingGroup(
            self,
            f"{construct_id}:MyASG",
            instance_type=ec2.InstanceType.of(
                instance_class=ec2.InstanceClass(resclass),
                instance_size=ec2.InstanceSize(ressize)
            ),
            machine_image=ec2.AmazonLinuxImage(
                user_data=ec2.UserData.custom(usrdata),
                edition=ec2.AmazonLinuxEdition.STANDARD,
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
            ),
            vpc=self.vpc,
            security_group=self.asgsg,
            key_name=f"{mykey}{region}",
            desired_capacity=desircap,
            min_capacity=mincap,
            max_capacity=maxcap,
            group_metrics=[asg.GroupMetrics.all()],
            vpc_subnets=ec2.SubnetSelection(subnet_group_name=ressubgrp,one_per_az=True),
        )
        if resmon == True:
            cw.CfnAlarm(
                self,
                f"{construct_id}MyASGAlarm",
                comparison_operator=("LessThanOrEqualToThreshold"),
                evaluation_periods=3,
                actions_enabled=False,
                datapoints_to_alarm=2,
                threshold=0,
                dimensions=[
                    dict(
                        name="AutoScalingGroupName",
                        value=self.asg.auto_scaling_group_name
                    )
                ],
                namespace=("AWS/AutoScaling"),
                metric_name=("GroupInServiceInstances"),
                period=core.Duration.minutes(1).to_seconds(),
                statistic="Minimum",
            )
        self.asg.scale_on_schedule(
            "PrescaleInTheMorning",
            schedule=asg.Schedule.cron(hour="9", minute="0"),
            desired_capacity=2
        )
        self.asg.scale_on_schedule(
            "AllowDownscalingAtNight",
            schedule=asg.Schedule.cron(hour="20", minute="0"),
            desired_capacity=0
        )
