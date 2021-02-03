import os
import sys
import boto3
import json
import time
import logging
import traceback
import requests
import xmltodict
from jinja2 import Template
region = os.environ['AWS_REGION']
logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3 = boto3.client('s3')
ec2 = boto3.client('ec2', region_name=region)

def fileupload(mycfgfile, bucketname, myobj):
    try:
        with open(mycfgfile, "rb") as data:
            response = s3.upload_fileobj(data, bucketname, myobj)
            logger.info('S3: Upload object Success: {}'.format(mycfgfile))
            return response
    except Exception as e:
        logger.info('S3: Creation of folder Error: {}'.format(e))


def createfolder(bucketname, folder):
    # create config folder to vpn files
    try:
        response = s3.put_object(Bucket=bucketname, Key=(folder))
        logger.info('S3: Creation of folder Success: {}'.format(folder))
        return response
    except Exception as e:
        logger.info('S3: Creation of folder Error: {}'.format(e))

def deletevpnfolder(bucketname, folder):
    # remove folder and vpn files
    try:
        response = s3.list_objects_v2(Bucket=bucketname, Prefix=folder)
        for obj in response['Contents']:
            # remove content
            if folder != obj['Key']:
                s3.delete_object(Bucket=bucketname, Key=obj['Key'])
                logger.info('S3: Deletion of object Success: {}'.format(obj['Key']))
        #remove folder
        s3.delete_object(Bucket=bucketname, Key=folder)
        logger.info('S3: Deletion of folder Success: {}'.format(folder))
        return response
    except Exception as e:
        logger.info('S3: Deletion of folder Error: {}'.format(e))

def describevpn(vpnid):
    # Get VPN Configuration XML
    try:
        response = ec2.describe_vpn_connections(
            VpnConnectionIds=[
                vpnid,
            ]
        )
        logger.info('EC2: VPN Configuration Received Success: {}'.format(vpnid))
        return response
    except Exception as e:
        logger.info('EC2: VPN Configuration Error: {}'.format(e))

def lambda_handler(event, context):
    logger.info('event: {}'.format(event))
    logger.info('context: {}'.format(context))
    #region = event['region']
    vpnid = event['ResourceProperties']['0']['VPN']
    routetype = event['ResourceProperties']['0']['Route']
    bucketname = event['ResourceProperties']['0']['S3']
    mylocalip = event['ResourceProperties']['0']['InstIPv4']
    if 'LocalCidr' in event['ResourceProperties']['0']:
        localcidr = event['ResourceProperties']['0']['LocalCidr']
    if 'RemoteCidr' in event['ResourceProperties']['0']:
        remotecidr = event['ResourceProperties']['0']['RemoteCidr']
    mys3vpnfolder = f"vpn/{vpnid}/"
    mylocalfolder = '/tmp/'
    requestId = event['RequestId']
    stacktId = event['StackId']
    logresId = event['LogicalResourceId']
    response = {
        "Status": "SUCCESS",
        "RequestId": requestId,
        "StackId": stacktId,
        "LogicalResourceId": logresId,
        "PhysicalResourceId" : "None",
        "Reason": "Nothing to do",
        "Data": {}
    }
    try:
        if event['RequestType'] == 'Delete':
            phyresId = event['PhysicalResourceId']
            # get vpn configuration
            deletevpnfolder(bucketname,mys3vpnfolder)
            response["Status"] = "SUCCESS"
            response["Reason"] = ("VPN Config deletion succeed!")
        elif event['RequestType'] == 'Create':
            # get vpn configuration
            vpn = describevpn(vpnid)
            # create config folder to vpn files
            createfolder(bucketname,mys3vpnfolder)
            # read template files
            with open('racoon_conf.tmpl') as f:
                racoon_conf = f.read()
            templaterac = Template(racoon_conf)
            with open('ipsec_tools_conf.tmpl') as f:
                ipsec_tools_conf = f.read()
            templateips = Template(ipsec_tools_conf)
            with open('ipsec_conf_fsw.tmpl') as f:
                ipsec_conf_fsw = f.read()
            templatefsw = Template(ipsec_conf_fsw)
            with open('ipsec_conf_osw.tmpl') as f:
                ipsec_conf_osw = f.read()
            templateosw = Template(ipsec_conf_osw)
            with open('bgpd_conf.tmpl') as f:
                bgpd_conf = f.read()
            templatequa = Template(bgpd_conf)
            with open('rc_conf.tmpl') as f:
                rc_conf = f.read()
            templaterc = Template(rc_conf)
            # parse configuration
            myvpnconfig = vpn['VpnConnections'][0]['CustomerGatewayConfiguration']
            myvpnxml = xmltodict.parse(myvpnconfig)
            tunnels = myvpnxml['vpn_connection']['ipsec_tunnel']
            # set iterator
            tnum = 1
            for tun in tunnels:
                # get variables
                cgw_out_addr = tun['customer_gateway']['tunnel_outside_address']['ip_address']
                cgw_in_addr = tun['customer_gateway']['tunnel_inside_address']['ip_address']
                cgw_in_cidr = tun['customer_gateway']['tunnel_inside_address']['network_cidr']
                if routetype == 'bgp':
                    cgw_bgp_asn = tun['customer_gateway']['bgp']['asn']
                    cgw_bgp_ht = tun['customer_gateway']['bgp']['hold_time']
                    vgw_bgp_asn = tun['vpn_gateway']['bgp']['asn']
                    vgw_bgp_ht = tun['vpn_gateway']['bgp']['hold_time']
                vgw_out_addr = tun['vpn_gateway']['tunnel_outside_address']['ip_address']
                vgw_in_addr = tun['vpn_gateway']['tunnel_inside_address']['ip_address']
                vgw_in_cidr = tun['vpn_gateway']['tunnel_inside_address']['network_cidr']
                ike_authentication_protocol = tun['ike']['authentication_protocol']
                ike_encryption_protocol = ''.join(tun['ike']['encryption_protocol'].split('-')[:2])
                ike_lifetime = tun['ike']['lifetime']
                ike_perfect_forward_secrecy = tun['ike']['perfect_forward_secrecy'][-1]
                ike_mode = tun['ike']['mode']
                ike_pre_shared_key = tun['ike']['pre_shared_key']
                ipsec_protocol = tun['ipsec']['protocol']
                ipsec_authentication_protocol = tun['ipsec']['authentication_protocol']
                ipsec_encryption_protocol = ''.join(tun['ipsec']['encryption_protocol'].split('-')[:2])
                ipsec_lifetime = tun['ipsec']['lifetime']
                ipsec_perfect_forward_secrecy = tun['ipsec']['perfect_forward_secrecy'][-1]
                ipsec_mode = tun['ipsec']['mode']
                ipsec_clear_df_bit = tun['ipsec']['clear_df_bit']
                ipsec_fragmentation_before_encryption = tun['ipsec']['fragmentation_before_encryption']
                ipsec_tcp_mss_adjustment = tun['ipsec']['tcp_mss_adjustment']
                dpd_delay = tun['ipsec']['dead_peer_detection']['interval']
                dpd_retry = tun['ipsec']['dead_peer_detection']['retries']
                # generate config files
                # secret file for racoon
                mycfgfile = f"{mylocalfolder}{vpnid}.secrets"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print('#Tunnel {0}\n{1}\t{2}'.format(tnum, vgw_out_addr, ike_pre_shared_key))
                # secret file for openswan/libreswan
                mycfgfile = f"{mylocalfolder}ipsec.secrets"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print('#Tunnel {0}\n{1} {2} : PSK "{3}"'.format(tnum, cgw_out_addr, vgw_out_addr, ike_pre_shared_key))
                # racoon.conf
                mycfgfile = f"{mylocalfolder}racoon.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templaterac.render(
                        tnum = tnum,
                        vgw_out_addr = vgw_out_addr,
                        ike_mode = ike_mode,
                        ike_lifetime = ike_lifetime,
                        ike_encryption_protocol = ike_encryption_protocol,
                        ike_authentication_protocol = ike_authentication_protocol,
                        ike_perfect_forward_secrecy = ike_perfect_forward_secrecy,
                        dpd_delay = dpd_delay,
                        dpd_retry = dpd_retry,
                        cgw_in_addr = cgw_in_addr,
                        cgw_in_cidr = cgw_in_cidr,
                        vgw_in_addr = vgw_in_addr,
                        vgw_in_cidr = vgw_in_cidr,
                        mylocalip = mylocalip,
                        cgw_out_addr = cgw_out_addr,
                        ipsec_perfect_forward_secrecy = ipsec_perfect_forward_secrecy,
                        ipsec_encryption_protocol = ipsec_encryption_protocol,
                        ipsec_authentication_protocol = '_'.join(ipsec_authentication_protocol.split('-')[:2]),
                        ipsec_lifetime = ipsec_lifetime
                    )
                )
                # ipsec-tools.conf
                mycfgfile = f"{mylocalfolder}ipsec-tools.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templateips.render(
                        tnum = tnum,
                        localcidr = localcidr,
                        remotecidr = remotecidr,
                        cgw_in_addr = cgw_in_addr,
                        cgw_in_cidr = cgw_in_cidr,
                        vgw_in_addr = vgw_in_addr,
                        vgw_in_cidr = vgw_in_cidr,
                        mylocalip = mylocalip,
                        cgw_out_addr = cgw_out_addr,
                        vgw_out_addr = vgw_out_addr
                    )
                )
                # vpnid.conf
                mycfgfile = f"{mylocalfolder}{vpnid}.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templatefsw.render(
                        tnum = tnum,
                        cgw_out_addr = cgw_out_addr,
                        vgw_out_addr = vgw_out_addr,
                        cgw_in_addr = cgw_in_addr,
                        cgw_in_cidr = cgw_in_cidr,
                        vgw_in_addr = vgw_in_addr,
                        vgw_in_cidr = vgw_in_cidr,
                        ipsec_mode = ipsec_mode,
                        ike_encryption_protocol = ike_encryption_protocol,
                        ike_authentication_protocol = ike_authentication_protocol,
                        ike_lifetime = int(ike_lifetime)/3600,
                        ipsec_encryption_protocol = ipsec_encryption_protocol,
                        ipsec_authentication_protocol = (ipsec_authentication_protocol.split('-')[1]),
                        ipsec_lifetime = int(ipsec_lifetime)/3600,
                        dpd_delay = int(dpd_delay),
                        dpdtimeout = int(dpd_retry)*int(dpd_delay)
                    )
                )
                # ipsec.conf
                mycfgfile = f"{mylocalfolder}ipsec.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templateosw.render(
                        tnum = tnum,
                        cgw_out_addr = cgw_out_addr,
                        vgw_out_addr = vgw_out_addr,
                        cgw_in_addr = cgw_in_addr,
                        cgw_in_cidr = cgw_in_cidr,
                        vgw_in_addr = vgw_in_addr,
                        vgw_in_cidr = vgw_in_cidr,
                        ipsec_mode = ipsec_mode,
                        ike_encryption_protocol = ike_encryption_protocol,
                        ike_authentication_protocol = ike_authentication_protocol,
                        ike_lifetime = ike_lifetime,
                        ipsec_encryption_protocol = ipsec_encryption_protocol,
                        ipsec_authentication_protocol = (ipsec_authentication_protocol.split('-')[1]),
                        ipsec_lifetime = ipsec_lifetime,
                        dpd_delay = int(dpd_delay),
                        dpdtimeout = int(dpd_retry)*int(dpd_delay)
                    )
                )
                # rc.conf
                mycfgfile = f"{mylocalfolder}rc.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templaterc.render(
                        tnum = tnum,
                        cgw_in_addr = cgw_in_addr,
                        vgw_in_addr = vgw_in_addr,
                        mylocalip = mylocalip,
                        cgw_out_addr = cgw_out_addr,
                        vgw_out_addr = vgw_out_addr
                    )
                )
                if routetype == 'bgp':
                    # bgp.conf
                    mycfgfile = f"{mylocalfolder}bgp.conf"
                    if tnum == 1:
                        sys.stdout = open(mycfgfile, 'w')
                    else:
                        sys.stdout = open(mycfgfile, 'a')
                    print(
                        templatequa.render(
                            tnum = tnum,
                            cgw_bgp_asn = cgw_bgp_asn,
                            cgw_bgp_ht = cgw_bgp_ht,
                            vgw_in_addr = vgw_in_addr,
                            vgw_bgp_asn = vgw_bgp_asn
                        )
                    )
                tnum += 1
            f.close()
            # upload files
            # racoon.conf
            mycfgfile = f"{mylocalfolder}racoon.conf"
            myobj = f"{mys3vpnfolder}racoon.conf"
            fileupload(mycfgfile, bucketname, myobj)
            # ipsec-tools.conf
            mycfgfile = f"{mylocalfolder}ipsec-tools.conf"
            myobj = f"{mys3vpnfolder}ipsec-tools.conf"
            fileupload(mycfgfile, bucketname, myobj)
            # vpnid.conf
            mycfgfile = f"{mylocalfolder}{vpnid}.conf"
            myobj = f"{mys3vpnfolder}{vpnid}.conf"
            fileupload(mycfgfile, bucketname, myobj)
            # ipsec.conf
            mycfgfile = f"{mylocalfolder}ipsec.conf"
            myobj = f"{mys3vpnfolder}ipsec.conf"
            fileupload(mycfgfile, bucketname, myobj)
            # rc.conf
            mycfgfile = f"{mylocalfolder}rc.conf"
            myobj = f"{mys3vpnfolder}rc.conf"
            fileupload(mycfgfile, bucketname, myobj)
            if routetype == 'bgp':
                # bgp.conf
                mycfgfile = f"{mylocalfolder}bgp.conf"
                fileupload(mycfgfile, bucketname, myobj)
            # vpnid.secrets
            mycfgfile = f"{mylocalfolder}{vpnid}.secrets"
            myobj = f"{mys3vpnfolder}{vpnid}.secrets"
            fileupload(mycfgfile, bucketname, myobj)
            # ipsec.secrets
            mycfgfile = f"{mylocalfolder}ipsec.secrets"
            myobj = f"{mys3vpnfolder}ipsec.secrets"
            fileupload(mycfgfile, bucketname, myobj)
            phyresId = vpnid
            response["Status"] = "SUCCESS"
            response["Reason"] = ("Configuration upload succeed!")
            response["PhysicalResourceId"] = phyresId
            response["Data"] = { "VPNid" : phyresId }
        else:
            phyresId = event['PhysicalResourceId']
            # get vpn configuration
            describevpn(vpnid)
            # read template files
            with open('racoon_conf.tmpl') as f:
                racoon_conf = f.read()
            templaterac = Template(racoon_conf)
            with open('ipsec_tools_conf.tmpl') as f:
                ipsec_tools_conf = f.read()
            templateips = Template(ipsec_tools_conf)
            with open('ipsec_conf_fsw.tmpl') as f:
                ipsec_conf_fsw = f.read()
            templatefsw = Template(ipsec_conf_fsw)
            with open('ipsec_conf_osw.tmpl') as f:
                ipsec_conf_osw = f.read()
            templateosw = Template(ipsec_conf_osw)
            with open('bgpd_conf.tmpl') as f:
                bgpd_conf = f.read()
            templatequa = Template(bgpd_conf)
            with open('rc_conf.tmpl') as f:
                rc_conf = f.read()
            templaterc = Template(rc_conf)
            # parse configuration
            myvpnconfig = vpn['VpnConnections'][0]['CustomerGatewayConfiguration']
            myvpnxml = xmltodict.parse(myvpnconfig)
            tunnels = myvpnxml['vpn_connection']['ipsec_tunnel']
            # set iterator
            tnum = 1
            for tun in tunnels:
                # get variables
                cgw_out_addr = tun['customer_gateway']['tunnel_outside_address']['ip_address']
                cgw_in_addr = tun['customer_gateway']['tunnel_inside_address']['ip_address']
                cgw_in_cidr = tun['customer_gateway']['tunnel_inside_address']['network_cidr']
                if routetype == 'bgp':
                    cgw_bgp_asn = tun['customer_gateway']['bgp']['asn']
                    cgw_bgp_ht = tun['customer_gateway']['bgp']['hold_time']
                    vgw_bgp_asn = tun['vpn_gateway']['bgp']['asn']
                    vgw_bgp_ht = tun['vpn_gateway']['bgp']['hold_time']
                vgw_out_addr = tun['vpn_gateway']['tunnel_outside_address']['ip_address']
                vgw_in_addr = tun['vpn_gateway']['tunnel_inside_address']['ip_address']
                vgw_in_cidr = tun['vpn_gateway']['tunnel_inside_address']['network_cidr']
                ike_authentication_protocol = tun['ike']['authentication_protocol']
                ike_encryption_protocol = ''.join(tun['ike']['encryption_protocol'].split('-')[:2])
                ike_lifetime = tun['ike']['lifetime']
                ike_perfect_forward_secrecy = tun['ike']['perfect_forward_secrecy'][-1]
                ike_mode = tun['ike']['mode']
                ike_pre_shared_key = tun['ike']['pre_shared_key']
                ipsec_protocol = tun['ipsec']['protocol']
                ipsec_authentication_protocol = tun['ipsec']['authentication_protocol']
                ipsec_encryption_protocol = ''.join(tun['ipsec']['encryption_protocol'].split('-')[:2])
                ipsec_lifetime = tun['ipsec']['lifetime']
                ipsec_perfect_forward_secrecy = tun['ipsec']['perfect_forward_secrecy'][-1]
                ipsec_mode = tun['ipsec']['mode']
                ipsec_clear_df_bit = tun['ipsec']['clear_df_bit']
                ipsec_fragmentation_before_encryption = tun['ipsec']['fragmentation_before_encryption']
                ipsec_tcp_mss_adjustment = tun['ipsec']['tcp_mss_adjustment']
                dpd_delay = tun['ipsec']['dead_peer_detection']['interval']
                dpd_retry = tun['ipsec']['dead_peer_detection']['retries']
                # generate config files
                # secret file for racoon
                mycfgfile = f"{mylocalfolder}{vpnid}.secrets"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print('#Tunnel {1}\n{2}\t{3}'.format(tnum, vgw_out_addr, ike_pre_shared_key))
                # secret file for openswan/libreswan
                mycfgfile = f"{mylocalfolder}ipsec.secrets"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print('#Tunnel {1}\n{2} {3} : PSK "{4}"'.format(tnum, cgw_out_addr, vgw_out_addr, ike_pre_shared_key))
                # racoon.conf
                mycfgfile = f"{mylocalfolder}racoon.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templaterac.render(
                        tnum = tnum,
                        vgw_out_addr = vgw_out_addr,
                        ike_mode = ike_mode,
                        ike_lifetime = ike_lifetime,
                        ike_encryption_protocol = ike_encryption_protocol,
                        ike_authentication_protocol = ike_authentication_protocol,
                        ike_perfect_forward_secrecy = ike_perfect_forward_secrecy,
                        dpd_delay = dpd_delay,
                        dpd_retry = dpd_retry,
                        cgw_in_addr = cgw_in_addr,
                        cgw_in_cidr = cgw_in_cidr,
                        vgw_in_addr = vgw_in_addr,
                        vgw_in_cidr = vgw_in_cidr,
                        mylocalip = mylocalip,
                        cgw_out_addr = cgw_out_addr,
                        ipsec_perfect_forward_secrecy = ipsec_perfect_forward_secrecy,
                        ipsec_encryption_protocol = ipsec_encryption_protocol,
                        ipsec_authentication_protocol = '_'.join(ipsec_authentication_protocol.split('-')[:2]),
                        ipsec_lifetime = ipsec_lifetime
                    )
                )
                # ipsec-tools.conf
                mycfgfile = f"{mylocalfolder}ipsec-tools.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templateips.render(
                        tnum = tnum,
                        localcidr = localcidr,
                        remotecidr = remotecidr,
                        cgw_in_addr = cgw_in_addr,
                        cgw_in_cidr = cgw_in_cidr,
                        vgw_in_addr = vgw_in_addr,
                        vgw_in_cidr = vgw_in_cidr,
                        mylocalip = mylocalip,
                        cgw_out_addr = cgw_out_addr,
                        vgw_out_addr = vgw_out_addr
                    )
                )
                # vpnid.conf
                mycfgfile = f"{mylocalfolder}{vpnid}.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templatefsw.render(
                        tnum = tnum,
                        cgw_out_addr = cgw_out_addr,
                        vgw_out_addr = vgw_out_addr,
                        cgw_in_addr = cgw_in_addr,
                        cgw_in_cidr = cgw_in_cidr,
                        vgw_in_addr = vgw_in_addr,
                        vgw_in_cidr = vgw_in_cidr,
                        ipsec_mode = ipsec_mode,
                        ike_encryption_protocol = ike_encryption_protocol,
                        ike_authentication_protocol = ike_authentication_protocol,
                        ike_lifetime = int(ike_lifetime)/3600,
                        ipsec_encryption_protocol = ipsec_encryption_protocol,
                        ipsec_authentication_protocol = (ipsec_authentication_protocol.split('-')[1]),
                        ipsec_lifetime = int(ipsec_lifetime)/3600,
                        dpd_delay = int(dpd_delay),
                        dpdtimeout = int(dpd_retry)*int(dpd_delay)
                    )
                )
                # ipsec.conf
                mycfgfile = f"{mylocalfolder}ipsec.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templateosw.render(
                        tnum = tnum,
                        cgw_out_addr = cgw_out_addr,
                        vgw_out_addr = vgw_out_addr,
                        cgw_in_addr = cgw_in_addr,
                        cgw_in_cidr = cgw_in_cidr,
                        vgw_in_addr = vgw_in_addr,
                        vgw_in_cidr = vgw_in_cidr,
                        ipsec_mode = ipsec_mode,
                        ike_encryption_protocol = ike_encryption_protocol,
                        ike_authentication_protocol = ike_authentication_protocol,
                        ike_lifetime = ike_lifetime,
                        ipsec_encryption_protocol = ipsec_encryption_protocol,
                        ipsec_authentication_protocol = (ipsec_authentication_protocol.split('-')[1]),
                        ipsec_lifetime = ipsec_lifetime,
                        dpd_delay = int(dpd_delay),
                        dpdtimeout = int(dpd_retry)*int(dpd_delay)
                    )
                )
                # rc.conf
                mycfgfile = f"{mylocalfolder}rc.conf"
                if tnum == 1:
                    sys.stdout = open(mycfgfile, 'w')
                else:
                    sys.stdout = open(mycfgfile, 'a')
                print(
                    templaterc.render(
                        tnum = tnum,
                        cgw_in_addr = cgw_in_addr,
                        vgw_in_addr = vgw_in_addr,
                        mylocalip = mylocalip,
                        cgw_out_addr = cgw_out_addr,
                        vgw_out_addr = vgw_out_addr
                    )
                )
                if routetype == 'bgp':
                    # bgp.conf
                    mycfgfile = f"{mylocalfolder}bgp.conf"
                    if tnum == 1:
                        sys.stdout = open(mycfgfile, 'w')
                    else:
                        sys.stdout = open(mycfgfile, 'a')
                    print(
                        templatequa.render(
                            tnum = tnum,
                            cgw_bgp_asn = cgw_bgp_asn,
                            cgw_bgp_ht = cgw_bgp_ht,
                            vgw_in_addr = vgw_in_addr,
                            vgw_bgp_asn = vgw_bgp_asn
                        )
                    )
                tnum += 1
            f.close()
            # upload files overwrite old
            # racoon.conf
            mycfgfile = f"{mylocalfolder}racoon.conf"
            myobj = f"{mys3vpnfolder}racoon.conf"
            fileupload(mycfgfile, bucketname, myobj)
            # ipsec-tools.conf
            mycfgfile = f"{mylocalfolder}ipsec-tools.conf"
            myobj = f"{mys3vpnfolder}ipsec-tools.conf"
            fileupload(mycfgfile, bucketname, myobj)
            # vpnid.conf
            mycfgfile = f"{mylocalfolder}{vpnid}.conf"
            myobj = f"{mys3vpnfolder}{vpnid}.conf"
            fileupload(mycfgfile, bucketname, myobj)
            # ipsec.conf
            mycfgfile = f"{mylocalfolder}ipsec.conf"
            myobj = f"{mys3vpnfolder}ipsec.conf"
            fileupload(mycfgfile, bucketname, myobj)
            # rc.conf
            mycfgfile = f"{mylocalfolder}rc.conf"
            myobj = f"{mys3vpnfolder}rc.conf"
            fileupload(mycfgfile, bucketname, myobj)
            if routetype == 'bgp':
                # bgp.conf
                mycfgfile = f"{mylocalfolder}bgp.conf"
                myobj = f"{mys3vpnfolder}bgp.conf"
                fileupload(mycfgfile, bucketname, myobj)
            # vpnid.secrets
            mycfgfile = f"{mylocalfolder}{vpnid}.secrets"
            myobj = f"{mys3vpnfolder}{vpnid}.secrets"
            fileupload(mycfgfile, bucketname, myobj)
            # ipsec.secrets
            mycfgfile = f"{mylocalfolder}ipsec.secrets"
            myobj = f"{mys3vpnfolder}ipsec.secrets"
            fileupload(mycfgfile, bucketname, myobj)
            phyresId = vpnid
            response["Status"] = "SUCCESS"
            response["Reason"] = ("Configuration upload succeed!")
            response["PhysicalResourceId"] = phyresId
            response["Data"] = { "VPNid" : phyresId }
    except Exception as e:
        response = {}
        logger.error('ERROR: {}'.format(e))
        traceback.print_exc()
        response["Status"] = "FAILED"
        response["Reason"] = str(e)
    logger.info('Sending Response')
    logger.info('response: {}'.format(response))
    response_data = json.dumps(response)
    headers = {
        'content-type': '',
        'content-length': str(len(response_data))
    }
    try:
        requests.put(event['ResponseURL'],data=response_data,headers=headers)
        logger.info('CloudFormation returned status code: {}'.format(response["Status"]))
        logger.info('CloudFormation returned Reason: {}'.format(response["Reason"]))
    except Exception as e:
        logger.info('send(..) failed executing requests.put(..): {}'.format(e))
        raise
    return response