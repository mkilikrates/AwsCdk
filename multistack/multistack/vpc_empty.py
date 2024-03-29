#### How to call this file inside app.py file and options
# VPCStack = VPC(app, "MY-VPC", env=myenv, res = 'vpc', cidrid = 0, natgw = 3, maxaz = 3, ipstack = ipstack)
# where:
# VPCStack ==> Name of stack, used if you will import values from it in another stack (Mandatory)
# VPC ==> reference to name of this script vpc_empty.py on import (Mandatory)
# MY-VPC ==> Name of contruct, you can use on cdk (cdk list, cdk deploy or cdk destroy). (Mandatory) This is the name of Cloudformation Template in cdk.out dir (MY-VPC.template.json)
# env ==> Environment to be used on this script (Account and region) (Mandatory)
# res ==> resource name to be used in this script, see it bellow in resourcesmap.cfg (Mandatory)
# cidrid ==> index id (int) cidr to be used on this vpc, see it bellow in zonemap.cfg (Mandatory)
# maxaz ==> Number of Availability zones (int) that this script will create resources (Mandatory)
# ipstack ==> if will be just ipv4 or dualstack (ipv6) (Mandatory)

#### How to create a resource information on resourcesmap.cfg for this template
# {
#     "vpc": {
#         "NAME": "protectedvpc", ####==> It will be used to create Tag Name associated with this resource. (Mandatory) the name will be like <constructname>/<vpcname>
#         "SUBNETS": [ ###==> List of subnets and attributes of each subnet. Created in AZs according to maxaz. (Optional) PS if not given the cidr will be splited in the number of subnets created.
#             {
#                 "PUBLIC": [ ###==> subnet type. (Mandatory) - https://docs.aws.amazon.com/cdk/api/latest/python/aws_cdk.aws_ec2/SubnetType.html#aws_cdk.aws_ec2.SubnetType
#                     {
#                         "CIDR": 24, ###==> CIDR Notation (Optional) - https://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing#:~:text=CIDR%20notation%20is%20a%20compact,bits%20in%20the%20network%20mask.
#                         "NAME": "DMZ", ###==> It will be used to create Tag Name associated with this resource (Optional). Since it will create in each AZ the name will be like <constructname>/<vpcname>/<subnetname><Subnet[aznumber]>
#                         "NETFWRT": [  ###==> List of cidrs to be created in route-table for this subnet associated with Network Firewall endpoint in same AZ. (Optional)
#                             "10.0.0.0/8",
#                             "100.64.0.0/10"
#                         ]
#                     }
#                 ]
#             },
#             {
#                 "ISOLATED": [
#                     {
#                         "CIDR": 23,
#                         "NAME": "Protected",
#                         "NETFWINC": true,
#                         "TGWRT": [  ###==> List of cidrs to be created in route-table for this subnet associated with Transit Gateway. (Optional)
#                             "192.168.0.0/16",
#                             "100.64.0.0/10"
#                         ]
#                     }
#                 ]
#             }
#         ],
#         "TAGS": [
#             {
#                 "Env": "staging" ###==> Any tag in this format { "key" : "value"}. (Optional)
#             }
#         ]
#     }
# }
#### How to use a resource information on zonemap.cfg for this template
# {
#     "Mappings": {  ###==> Vide Cloudformation Mappings - https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/mappings-section-structure.html
#         "RegionMap": {
#             "eu-north-1": {  ###==> Region name
#                 "CIDR": [  ###==> CIDR list created for this region to be allocated using cidrid index
#                     "10.0.0.0/16", ###==> python index (0)
#                     "10.1.0.0/16", ###==> python index (1)
#                     "10.2.0.0/16", ###==> python index (2)
#                     "10.3.0.0/16" ###==> python index (3) ...
#                 ],
#             },
#             "me-south-1": {
#                 "CIDR": [
#                     "10.16.0.0/16",
#                     "10.17.0.0/16",
#                     "10.18.0.0/16",
#                     "10.19.0.0/16"
#                 ],
#             }
#         }
#     }
# }


import os
import json
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ram as ram,
    aws_route53 as r53,
    aws_route53_targets as r53tgs,
    core
)
account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"])
region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"])

class VPC(core.Stack):
    def __init__(self, scope: core.Construct, construct_id: str, res, vpcid, ipstack, cidrid, natgw, maxaz, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # get imported objects
        if res == '':
            if vpcid != '':
                self.vpc = ec2.Vpc.from_lookup(
                    self,
                    id=f"{construct_id}",
                    vpc_id=vpcid
                )
            else:
                self.vpc = ec2.Vpc.from_lookup(
                    self,
                    'DEFAULT-VPC',
                    is_default=True
                )
        else:
            self.cidrid = int(cidrid)
            self.natgw = int(natgw)
            self.maxaz = int(maxaz)
            self.ipstack = ipstack
            res = res
            # get prefix list from file to allow traffic from the office
            res = res
            resconf = "resourcesmap.cfg"
            with open(resconf) as resfile:
                resmap = json.load(resfile)
            with open('zonemap.cfg') as zonefile:
                zonemap = json.load(zonefile)
            # get prefix list from file to allow traffic from the office
            vcpcidr = zonemap['Mappings']['RegionMap'][region]['CIDR'][self.cidrid]
            resname = resmap['Mappings']['Resources'][res]['NAME']
            if 'AZS' in resmap['Mappings']['Resources'][res]:
                azs = resmap['Mappings']['Resources'][res]['AZS']
                self.node.set_context(
                    key=f'availability-zones:account={self.account}:region={self.region}',
                    value=azs
                )
            if 'SUBNETS' in resmap['Mappings']['Resources'][res]:
                self.sub = []
                for subtype in resmap['Mappings']['Resources'][res]['SUBNETS']:
                    if 'PUBLIC' in subtype:
                        for sub in subtype['PUBLIC']:
                            self.sub.append(
                                ec2.SubnetConfiguration(
                                    name=sub['NAME'],
                                    subnet_type=ec2.SubnetType.PUBLIC,
                                    cidr_mask=sub['CIDR']
                                )
                            )
                    if 'PRIVATE' in subtype:
                        for sub in subtype['PRIVATE']:
                            self.sub.append(
                                ec2.SubnetConfiguration(
                                    name=sub['NAME'],
                                    subnet_type=ec2.SubnetType.PRIVATE,
                                    cidr_mask=sub['CIDR']
                                )
                            )
                    if 'ISOLATED' in subtype:
                        for sub in subtype['ISOLATED']:
                            self.sub.append(
                                ec2.SubnetConfiguration(
                                    name=sub['NAME'],
                                    subnet_type=ec2.SubnetType.ISOLATED,
                                    cidr_mask=sub['CIDR']
                                )
                            )
            else:
                self.sub = None
            # create simple vpc
            self.vpc = ec2.Vpc(self,
                f"{resname}",
                cidr=vcpcidr,
                max_azs=self.maxaz,
                nat_gateways=self.natgw,
                subnet_configuration=self.sub
            )
            self.v4 = core.CfnOutput(
                self,
                f"{self.stack_name}:Ipv4Cidr",
                value=self.vpc.vpc_cidr_block,
                export_name=f"{self.stack_name}:Ipv4Cidr"
            )
            # share ram
            if 'Principals' in resmap['Mappings']['Resources'][res]:
                resprinc = resmap['Mappings']['Resources'][res]['Principals']
                arnlist = []
                if 'EXTERN' in resmap['Mappings']['Resources'][res]:
                    resallowext = resmap['Mappings']['Resources'][res]['EXTERN']
                else:
                    resallowext = False
                if 'subshare' in resmap['Mappings']['Resources'][res]:
                    for subgroup in resmap['Mappings']['Resources'][res]['subshare']:
                        subgrouplst = []
                        subgrouplst.append(self.vpc.select_subnets(subnet_group_name=subgroup).subnet_ids)
                        for each in subgrouplst:
                            arnlist.append(f"arn:{core.Aws.PARTITION}:ec2:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:subnet/{each}")
                else:
                    subgrouplst = self.vpc.select_subnets().subnet_ids
                    for each in subgrouplst:
                        arnlist.append(f"arn:{core.Aws.PARTITION}:ec2:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:subnet/{each}")
                self.ram = ram.CfnResourceShare(
                    self,
                    f"{construct_id}-ram",
                    name=resname,
                    allow_external_principals=resallowext,
                    principals=resprinc,
                    resource_arns=arnlist
                )
            # associate with private hosted zone
            if 'HZDOMAIN' in resmap['Mappings']['Resources'][res]:
                appdomain = resmap['Mappings']['Resources'][res]['HZDOMAIN']
                # get hosted zone id
                self.hz = r53.PrivateHostedZone.from_lookup(
                    self,
                    f"{construct_id}:Domain",
                    domain_name=appdomain,
                    private_zone=True
                )
                self.hz.add_vpc(vpc=self.vpc)
            elif 'DOMAIN' in resmap['Mappings']['Resources'][res]:
                appdomain = resmap['Mappings']['Resources'][res]['DOMAIN']
                # get hosted zone id
                self.hz = r53.PrivateHostedZone(
                    self,
                    f"{construct_id}:Domain",
                    zone_name = appdomain,
                    vpc=self.vpc
                )
            if 'MULTICIDR' in resmap['Mappings']['Resources'][res]:
                cidrs = resmap['Mappings']['Resources'][res]['MULTICIDR']
                if type(cidrs) == list:
                    index = 1
                    for i in cidrs:
                        ec2.CfnVPCCidrBlock(
                            self,
                            f"cidr-{index}",
                            vpc_id = self.vpc.vpc_id,
                            cidr_block = i,
                        )
                        index = index + 1
                else:
                    ec2.CfnVPCCidrBlock(
                        self,
                        "cidr",
                        vpc_id = self.vpc.vpc_id,
                        cidr_block = cidrs,
                    )
            if self.ipstack != 'Ipv4':
                # ipv6 on this vpc
                self.ipv6_block = ec2.CfnVPCCidrBlock(self, "Ipv6",
                    vpc_id=self.vpc.vpc_id,
                    amazon_provided_ipv6_cidr_block=True
                )
                # Create EgressOnlyInternetGateway
                egressonlygateway = ec2.CfnEgressOnlyInternetGateway(
                    self,
                    "EgressOnlyInternetGateway",
                    vpc_id=self.vpc.vpc_id
                )
                # Sniff out InternetGateway to use to assign ipv6 routes
                for child in self.vpc.node.children:
                    if isinstance(child, ec2.CfnInternetGateway):
                        internet_gateway = child
                        break
                else:
                    raise Exception("Couldn't find the InternetGateway of the VPC")
                #set counter to iterate with Fn.cidr select
                i = 0
                # Iterate on Public Subnet
                for subnet in self.vpc.public_subnets:
                    # set default route to IGW
                    subnet.add_route(
                        "DefaultIpv6Route",
                        router_id=internet_gateway.ref,
                        router_type=ec2.RouterType.GATEWAY,
                        destination_ipv6_cidr_block="::/0",
                    )
                    # allocate ipv6 to each subnet
                    assert isinstance(subnet.node.children[0], ec2.CfnSubnet)
                    subnet.node.children[0].ipv6_cidr_block = core.Fn.select(
                        i,
                        core.Fn.cidr(
                            core.Fn.select(
                                0,
                                self.vpc.vpc_ipv6_cidr_blocks
                            ),
                            len(self.vpc.public_subnets) + len(self.vpc.private_subnets) + len(self.vpc.isolated_subnets),
                            "64"
                        )
                    )
                    subnet.node.add_dependency(self.ipv6_block)
                    i = i + 1
                # Iterate on Private Subnet
                for subnet in self.vpc.private_subnets:
                    # set default route to IGW
                    subnet.add_route(
                        "DefaultIpv6Route",
                        router_id=egressonlygateway.ref,
                        router_type=ec2.RouterType.EGRESS_ONLY_INTERNET_GATEWAY,
                        destination_ipv6_cidr_block="::/0",
                    )
                    # allocate ipv6 to each subnet
                    assert isinstance(subnet.node.children[0], ec2.CfnSubnet)
                    subnet.node.children[0].ipv6_cidr_block = core.Fn.select(
                        i,
                        core.Fn.cidr(
                            core.Fn.select(
                                0,
                                self.vpc.vpc_ipv6_cidr_blocks
                            ),
                            len(self.vpc.public_subnets) + len(self.vpc.private_subnets) + len(self.vpc.isolated_subnets),
                            "64"
                        )
                    )
                    subnet.node.children[0].add_deletion_override('Properties.MapPublicIpOnLaunch')
                    subnet.node.children[0].assign_ipv6_address_on_creation=True
                    subnet.node.add_dependency(self.ipv6_block)
                    i = i + 1
                # Iterate on Isolated Subnet
                for subnet in self.vpc.isolated_subnets:
                    # allocate ipv6 to each subnet
                    assert isinstance(subnet.node.children[0], ec2.CfnSubnet)
                    subnet.node.children[0].ipv6_cidr_block = core.Fn.select(
                        i,
                        core.Fn.cidr(
                            core.Fn.select(
                                0,
                                self.vpc.vpc_ipv6_cidr_blocks
                            ),
                            len(self.vpc.public_subnets) + len(self.vpc.private_subnets) + len(self.vpc.isolated_subnets),
                            "64"
                        )
                    )
                    subnet.node.children[0].add_deletion_override('Properties.MapPublicIpOnLaunch')
                    subnet.node.children[0].assign_ipv6_address_on_creation=True
                    subnet.node.add_dependency(self.ipv6_block)
                    i = i + 1
                self.v6 = core.CfnOutput(
                    self,
                    f"{self.stack_name}:Ipv6Cidr",
                    value=core.Fn.select(0,self.vpc.vpc_ipv6_cidr_blocks),
                    # value= core.Token.as_string(self.vpc.vpc_ipv6_cidr_blocks),
                    export_name=f"{self.stack_name}:Ipv6Cidr"
                )
