#!/usr/bin/env python3
import os
from aws_cdk import core
from multistack.vpc_empty import VPC as VPC
from multistack.bastion import BastionStack as bastion
from multistack.vpcflow import flowlogs
from multistack.vpcendpoints import VPCEStack as vpce
from multistack.tgw_vgw import mygw
from multistack.asg import main as asg
from multistack.elb import alb
from multistack.rds import myrds as rds
from multistack.vpn import cvpn, s2svpn
from multistack.ec2_eip import EIP as eip
from multistack.decodevpn import S2SVPNS3 as vpns3
from multistack.ds import myds
from multistack.eks import EksStack as eks
from multistack.ecs import EcsStack as ecs
from multistack.eksapp import MyAppStack as eksapp
from multistack.netfw import internetfw as netfw
from multistack.ec2 import InstanceStack as instance
from multistack.eksctrl import (
    eksDNS as eksdns,
    eksELB as ekselb,
    eksING as eksing
    )
remoteregion = 'eu-west-1'
myenv = core.Environment(account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"]), region = os.environ.get("CDK_DEPLOY_REGION", os.environ["CDK_DEFAULT_REGION"]))
myenv2 = core.Environment(account = os.environ.get("CDK_DEPLOY_ACCOUNT", os.environ["CDK_DEFAULT_ACCOUNT"]), region = remoteregion)
route = 'bgp'
gwtype = 'tgw'
ipstack = 'Ipv4'
app = core.App()
VPCStack = VPC(app, "MY-VPC", env=myenv, res = 'inspectvpc', cidrid = 0, natgw = 3, maxaz = 3, ipstack = ipstack)
#FlowLogsStack = flowlogs(app, "MY-VPCFLOW", env=myenv, logfor = 'default', vpcid = VPCStack.vpc.vpc_id)
NetFWStack = netfw(app, "MYNETFW", env=myenv, vpcname = 'inspectvpc', res = 'netfwtgw', vpc = VPCStack.vpc)
GatewayStack = mygw(app, "MY-GATEWAY", env=myenv, gwtype = gwtype, gwid = '', res = 'tgwnetfw', route = route, ipstack = ipstack, vpc = VPCStack.vpc, vpcname = 'inspectvpc', bastionsg = '', tgwstack = '', cross = False)
BationStack = bastion(app, "MY-BASTION", env=myenv, res = 'bastion', preflst = True, allowsg = '', allowall = '', ipstack = ipstack, vpc = VPCStack.vpc)
VPCStack2 = VPC(app, "MY-VPC2", env=myenv, res = 'vpcsec', cidrid = 1, natgw = 0, maxaz = 3, ipstack = ipstack)
VPCStack2.add_dependency(NetFWStack)
GatewayStack2 = mygw(app, "MY-GATEWAY2", env=myenv, gwtype = gwtype, gwid = GatewayStack.gw.ref, res = 'tgwnetfw', route = route, ipstack = ipstack, vpc = VPCStack2.vpc, vpcname = 'vpcsec', bastionsg = '', tgwstack = GatewayStack, cross = False)
BationStack2 = bastion(app, "MY-BASTION2", env=myenv, res = 'bastionsimplepriv', preflst = True, allowsg = '', allowall = '', ipstack = ipstack, vpc = VPCStack2.vpc)
BationStack2.add_dependency(GatewayStack2)
#ASGStack = asg(app, "MY-ASG", env=myenv, res = 'simpletshoot', preflst = False, allowall = '', ipstack = ipstack, allowsg = BationStack.bastionsg, vpc = VPCStack.vpc).add_dependency(FlowLogsStack)
#VpcEndpointsStack = vpce(app, "MY-VPCENDPOINTS", env=myenv, res = 's3Endpoint', preflst = False, allowsg = '', allowall = '', ipstack = ipstack, vpc = VPCStack.vpc, vpcstack = VPCStack.stack_name)
EIPStack = eip(app, "MY-EIP", env=myenv, allocregion = remoteregion)
S2SVPNStack = s2svpn(app, "MY-VPN", env=myenv, gwtype = gwtype, route = route, res = 'vpncust', funct = '', ipfamily = 'ipv4', gwid = GatewayStack.gw, cgwaddr = EIPStack.mycustomresource, tgwrt = core.Fn.import_value(f"{GatewayStack.stack_name}:tgwrtSentToFWout"), tgwprop = core.Fn.import_value(f"{GatewayStack.stack_name}:tgwrtVPCsout"), tgwrtfunct = '', staticrt = [])
S2SVPNStack.add_dependency(NetFWStack)
#S3VPNStack = vpns3(app, "MY-S2SVPNS3", env=myenv, route = route, vpnid = 'vpn-0f3e7c12457f29fdf', vpnregion = remoteregion, funct ='', res = 'vpnsrvstrswbgp', vpc = VPCStack.vpc)
#RDSStack = rds(app, "MYRDS", env=myenv, res = 'rdsaurorapostgrsmall', vpc = VPCStack2.vpc, bastionsg = BationStack.bastionsg)
#ADStack = myds(app, "MYDS", env=myenv, res = 'dirserv', vpc = VPCStack.vpc)
#CVPNStack = cvpn(app, "MY-CVPN", env=myenv, res = 'cvpn', auth = ['mutual', 'federated'], vpc = VPCStack2.vpc, dirid = '')
#EKStack = eks(app, "myeks", env=myenv, res = 'myeksprivec2', preflst = True, allowsg = BationStack.bastionsg, allowall = '', ipstack = ipstack, role = '', vpc = VPCStack2.vpc)
#EKSDNSStack = eksdns(app, "dns-controller", env=myenv, ekscluster = EKStack.eksclust).add_dependency(target=EKStack)
#EKSELBStack = ekselb(app, "aws-elb-controller", env=myenv, ekscluster = EKStack.eksclust).add_dependency(target=EKStack)
#EKSINGStack = eksing(app, "aws-elb-controller", env=myenv, ekscluster = EKStack.eksclust).add_dependency(target=EKStack)
## use one or other 
#EKSAppStack = eksapp(app, "nginxs3", env=myenv, res = 'eksnlbbe', preflst = False, allowsg = '', allowall = 80, ekscluster = EKStack.eksclust, ipstack = ipstack, vpc = VPCStack2.vpc, elbsg = EKStack.lbsg)
#ECStack = ecs(app, "myecs", env=myenv, res = 'eksnlbbe', preflst = False, allowsg = BationStack.bastionsg, allowall = 443, ipstack = ipstack, vpc = VPCStack2.vpc)
#ELBStack = alb(app, "MY-ELB", env=myenv, res = 'elbfe', preflst = False, allowsg = '', allowall = 443, ipstack = ipstack, tgrt = ASGStack2.asg, vpc = VPCStack.vpc)
app.synth()
