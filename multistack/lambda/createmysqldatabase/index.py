import os
import sys
import logging
import pymysql
import boto3
import json
import traceback
import requests
region = os.environ['AWS_REGION']
mysql_timeout = 10
logger = logging.getLogger()
logger.setLevel(logging.INFO)
secret = boto3.client('secretsmanager', region_name=region)
def getsecretvalue(secret_name):
    try:
        action = secret.get_secret_value(SecretId=secret_name)
        return action
    except Exception as e:
        logger.info('SecretsMgr: Create Secret Error: {}'.format(e))
        raise e

def lambda_handler(event, context):
    logger.info('event: {}'.format(event))
    logger.info('context: {}'.format(context))
    requestId = event['RequestId']
    stacktId = event['StackId']
    logresId = event['LogicalResourceId']
    secstring = ''
    if 'PhysicalResourceId' in event:
        phyresId = event['PhysicalResourceId']
    else:
        phyresId = None
    response = {
        "Status": "SUCCESS",
        "RequestId": requestId,
        "StackId": stacktId,
        "LogicalResourceId": logresId,
        "PhysicalResourceId" : phyresId,
        "Reason": "Nothing to do",
        "Data": {}
    }
    if event['RequestType'] != 'Delete':
        try:
            if 'DataBase' in event['ResourceProperties']['0']:
                mysql_db = event['ResourceProperties']['0']['DataBase']
                logger.info('I got Database {}'.format(mysql_db))
            if 'SecretName' in event['ResourceProperties']['0']:
                secret_name = event['ResourceProperties']['0']['SecretName']
                logger.info('I got Secret ARN {}'.format(secret_name))
                try:
                    result = getsecretvalue(secret_name)
                    logger.info('Debug: {}'.format(result))
                    if 'SecretString' in result:
                        if result['SecretString'][0] == '{' and result['SecretString'][-1] == '}':
                            secstring = json.loads(result['SecretString'])
                        else:
                            secstring = result['SecretString']
                        logger.info('SecretsMgr: I got Secret Type {}'.format(type(secstring)))
                except Exception as e:
                    logger.error('SecretsMgr: Get Secret Error: {}'.format(e))
                if type(secstring) == dict:
                    mysql_host = secstring['host']
                    mysql_port = secstring['port']
                    mysql_user = secstring['username']
                    mysql_password = secstring['password']
                elif type(secstring) == str:
                    mysql_host = event['ResourceProperties']['0']['MysqlHost']
                    if 'MysqlPort' in event['ResourceProperties']['0']:
                        mysql_port = event['ResourceProperties']['0']['MysqlPort']
                    else:
                        mysql_port = 3306
                    mysql_user = event['ResourceProperties']['0']['MysqlUser']
                    mysql_password = secstring
            # connect to DB
            try:
                conn = pymysql.connect(host=mysql_host, port=mysql_port, user=mysql_user, passwd=mysql_password, connect_timeout=mysql_timeout)
                logger.info(f"SUCCESS: Connection to RDS MySQL {mysql_host}:{mysql_port} succeeded")
                with conn.cursor() as cur:
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS {mysql_db};")
                    cur.execute(f"SHOW DATABASES;")
                    databaseList = cur.fetchall()
                conn.commit()
            except pymysql.MySQLError as e:
                logger.error("ERROR: Unexpected error: Could not connect to MySQL instance.")
                logger.error(e)
            # generate response
            phyresId = mysql_db
            response["Status"] = "SUCCESS"
            response["Reason"] = ("Configuration succeed!")
            response["PhysicalResourceId"] = phyresId
            response["Data"]["DBList"] = databaseList
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
        logger.error('send(..) failed executing requests.put(..): {}'.format(e))
        raise
    return response