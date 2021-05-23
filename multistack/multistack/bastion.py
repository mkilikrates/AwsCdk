#### How to create a resource information on resourcesmap.cfg for this template
# {
#     "bastioncdk": { 
#         "NAME": "hostname",  ####==> It will be used to create Tag Name associated with this resource. (Mandatory)
#         "KEY": "mykeyname-", ####==> It will be used as part of key pair to login in the instance. It will be appended with region name like mykey-us-east-1 (Optional)
#         "MANAGPOL": "AdministratorAccess", ###==> If you want to attach a AWS managed policy (Optional)
#         "TAGS": [
#             {
#                 "Role": "Bastion" ###==> Any tag in this format { "key" : "value"}. (Optional)
#             }
#         ],
#         "SUBNETGRP": "Public", ###==> Subnet Group used on VPC creation. (Mandatory)
#         "USRFILE": "cdkBastion.cfg", ###==> Any user-data to be passed on first launch. (Optional)
#         "CLASS": "BURSTABLE3", ###==> Class of Instance. (Mandatory) - https://docs.aws.amazon.com/cdk/api/latest/python/aws_cdk.aws_ec2/InstanceClass.html#aws_cdk.aws_ec2.InstanceClass
#         "SIZE": "MEDIUM", ###==> Instance Size. (Mandatory) - https://docs.aws.amazon.com/cdk/api/latest/python/aws_cdk.aws_ec2/InstanceSize.html#aws_cdk.aws_ec2.InstanceSize
#         "VOLUMES": [ ###==> List of volumes, first root - https://docs.aws.amazon.com/cdk/api/latest/python/aws_cdk.aws_ec2/BlockDevice.html#aws_cdk.aws_ec2.BlockDevice
#             {
#                 "NAME": "/dev/xvda",
#                 "SIZE": 100,
#                 "CRYPT": false,
#                 "TYPE": "GP2"
#             }
#         ],
#         "min": 0, ###==> Used as minimum size for AutoScale Group
#         "max": 6, ###==> Used as maximum size for AutoScale Group
#         "desir": 1, ###==> Used as desirable size for AutoScale Group
#         "MONITOR": false, ###==> Used on AutoScale Group for increase or decrease Group Size in a given time
#         "INTERNET": false ###==> Allocate and Associate to Elastic IP
#     }
# }

#### How to use a resource information on zonemap.cfg for this template
# {
#     "Mappings": {  ###==> Vide Cloudformation Mappings - https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/mappings-section-structure.html
#         "RegionMap": {
#             "eu-north-1": {  ###==> Region name
#                 "PREFIXLIST": "pl-123abcxyz" ###==> Prefix list created for this region
#             },
#             "me-south-1": {
#                 "PREFIXLIST": "pl-5gas64ds6"
#             }
#         }
#     }
# }



import os
import json
from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    core,
)
account = core.Aws.ACCOUNT_ID
region = core.Aws.REGION
class BastionStack(core.Stack):
    def __init__(self, scope: core.Construct, construct_id: str, res, preflst, allowall, ipstack, vpc = ec2.Vpc, allowsg = ec2.SecurityGroup, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # get imported objects
        self.vpc = vpc
        self.ipstack = ipstack
        res = res
        resconf = "resourcesmap.cfg"
        with open(resconf) as resfile:
            resmap = json.load(resfile)
        with open('zonemap.cfg') as zonefile:
            zonemap = json.load(zonefile)
        # get prefix list from file to allow traffic from the office
        self.map = core.CfnMapping(
            self,
            f"{construct_id}Map",
            mapping=zonemap["Mappings"]["RegionMap"]
        )
        # create security group for bastion
        self.bastionsg = ec2.SecurityGroup(
            self,
            f"{construct_id}SG",
            allow_all_outbound=True,
            vpc=self.vpc
        )
        # add egress rule
        ec2.CfnSecurityGroupEgress(
            self,
            f"{construct_id}EgressAllIpv4",
            ip_protocol="-1",
            cidr_ip="0.0.0.0/0",
            group_id=self.bastionsg.security_group_id
        )
        if self.ipstack == 'Ipv6':
            ec2.CfnSecurityGroupEgress(
                self,
                f"{construct_id}EgressAllIpv6",
                ip_protocol="-1",
                cidr_ipv6="::/0",
                group_id=self.bastionsg.security_group_id
            )
        # add ingress rule
        if allowsg != '':
            self.bastionsg.add_ingress_rule(
                self.allowsg,
                ec2.Port.all_traffic()
            )
        if preflst == True:
            srcprefix = self.map.find_in_map(core.Aws.REGION, 'PREFIXLIST')
            self.bastionsg.add_ingress_rule(
                ec2.Peer.prefix_list(srcprefix),
                ec2.Port.all_traffic()
            )
        if allowall == True:
            self.bastionsg.add_ingress_rule(
                ec2.Peer.any_ipv4,
                ec2.Port.all_traffic()
            )
            if self.ipstack == 'Ipv6':
                self.bastionsg.add_ingress_rule(
                    ec2.Peer.any_ipv6,
                    ec2.Port.all_traffic()
                )
        if type(allowall) == int or type(allowall) == float:
            self.bastionsg.add_ingress_rule(
                ec2.Peer.any_ipv4(),
                ec2.Port.tcp(allowall)
            )
            if self.ipstack == 'Ipv6':
                self.bastionsg.add_ingress_rule(
                    ec2.Peer.any_ipv6(),
                    ec2.Port.tcp(allowall)
                )

        # get data for bastion resource
        resname = resmap['Mappings']['Resources'][res]['NAME']
        ressubgrp = resmap['Mappings']['Resources'][res]['SUBNETGRP']
        ressize = resmap['Mappings']['Resources'][res]['SIZE']
        resclass = resmap['Mappings']['Resources'][res]['CLASS']
        if 'MANAGPOL' in resmap['Mappings']['Resources'][res]:
            resmanpol = resmap['Mappings']['Resources'][res]['MANAGPOL']
        else:
            resmanpol = ''
        if 'VOLUMES' in resmap['Mappings']['Resources'][res]:
            myblkdev = []
            for vol in resmap['Mappings']['Resources'][res]['VOLUMES']:
                resvolname = vol['NAME']
                resvolsize = vol['SIZE']
                resvolcrypt = vol['CRYPT']
                if vol['TYPE'] == 'GP2':
                    resvoltype = ec2.EbsDeviceVolumeType.GP2
                elif vol['TYPE'] == 'GP3':
                    resvoltype = ec2.EbsDeviceVolumeType.GP3
                elif vol['TYPE'] == 'IO1':
                    resvoltype = ec2.EbsDeviceVolumeType.IO1
                elif vol['TYPE'] == 'IO2':
                    resvoltype = ec2.EbsDeviceVolumeType.IO2
                elif vol['TYPE'] == 'SC1':
                    resvoltype = ec2.EbsDeviceVolumeType.SC1
                elif vol['TYPE'] == 'ST1':
                    resvoltype = ec2.EbsDeviceVolumeType.ST1
                elif vol['TYPE'] == 'STANDARD':
                    resvoltype = ec2.EbsDeviceVolumeType.STANDARD
                myblkdev.append(ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_type=resvoltype,
                        volume_size=resvolsize,
                        encrypted=resvolcrypt,
                        delete_on_termination=True
                    )
                ))
        else:
            myblkdev = None
        if 'INTERNET' in resmap['Mappings']['Resources'][res]:
            reseip = resmap['Mappings']['Resources'][res]['INTERNET']
        else:
            reseip = False
        if 'KEY' in resmap['Mappings']['Resources'][res]:
            mykey = resmap['Mappings']['Resources'][res]['KEY'] + region
        else:
            mykey = ''
        if 'USRFILE' in resmap['Mappings']['Resources'][res]:
            usrdatafile = resmap['Mappings']['Resources'][res]['USRFILE']
        else:
            usrdatafile = ''
        usrdata = open(usrdatafile, "r").read()
        # create bastion host instance
        self.bastion = ec2.BastionHostLinux(
            self,
            f"{construct_id}",
            vpc=self.vpc,
            security_group=self.bastionsg,
            subnet_selection=ec2.SubnetSelection(subnet_group_name=ressubgrp,one_per_az=True),
            instance_type=ec2.InstanceType.of(
                instance_class=ec2.InstanceClass(resclass),
                instance_size=ec2.InstanceSize(ressize)
            ),
            machine_image=ec2.AmazonLinuxImage(
                edition=ec2.AmazonLinuxEdition.STANDARD,
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            ),
            block_devices=myblkdev,
            instance_name=f"{resname}-{region}",
        )
        # add tags
        for tagsmap in resmap['Mappings']['Resources'][res]['TAGS']:
            for k,v in tagsmap.items():
                core.Tags.of(self.bastion).add(k,v,include_resource_types=["AWS::EC2::Instance"])
        # add my key
        if mykey != '':
            self.bastion.instance.instance.add_property_override("KeyName", mykey)
        if usrdata != '':
            self.bastion.instance.add_user_data(usrdata)
        # create instance profile
        # add SSM permissions to update instance
        pol = iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSSMManagedInstanceCore')
        self.bastion.instance.role.add_managed_policy(pol)
        # add managed policy based on resourcemap
        if resmanpol !='':
            manpol = iam.ManagedPolicy.from_aws_managed_policy_name(resmanpol)
            self.bastion.instance.role.add_managed_policy(manpol)
        # allocate elastic ip
        if reseip == True:
            ec2.CfnEIP(
                self,
                f"{self}BastionEip",
                domain='vpc',
                instance_id=self.bastion.instance_id,
            )
        #     netint = []
        #     netint.append({"AssociatePublicIpAddress": "true", "DeviceIndex": "0"})
        #     self.bastion.instance.instance.add_property_override("NetworkInterfaces", netint)
        # output
        core.CfnOutput(
            self,
            f"{construct_id}:id",
            value=self.bastion.instance_id,
            export_name=f"{construct_id}:id"
        )
        core.CfnOutput(
            self,
            f"{construct_id}:sg",
            value=self.bastionsg.security_group_id,
            export_name=f"{construct_id}:sg"
        )
        core.CfnOutput(
            self,
            f"{construct_id}:ipv4",
            value=self.bastion.__getattribute__("instance_public_ip"),
            export_name=f"{construct_id}:ipv4"
        )
        if self.ipstack == 'Ipv6':
            self.bastion.instance.instance.add_property_override("Ipv6AddressCount", 1)

