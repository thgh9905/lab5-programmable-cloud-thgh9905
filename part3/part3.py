#!/usr/bin/env python3

import argparse
import os
import time
from pprint import pprint

import googleapiclient.discovery
import google.auth
import google.oauth2.service_account as service_account

#
# Use Google Service Account - See https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.service_account.html#module-google.oauth2.service_account
#
credentials = service_account.Credentials.from_service_account_file(filename='service-credentials.json')
project = os.getenv('GOOGLE_CLOUD_PROJECT') or 'FILL IN YOUR PROJECT'
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

#
# Stub code - just lists all instances
#
def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    return result.get('items', [])

def wait_for_operation(compute, project, zone, operation):
    print("Waiting for operation to finish...")
    while True:
        result = (compute.zoneOperations().get(project=project, zone=zone, operation=operation).execute())

        if result["status"] == "DONE":
            print("done.")
            if "error" in result:
                raise Exception(result["error"])
            return result

        time.sleep(1)

def create_instance(compute, project, zone, name, startup_script, vm2_startup_script, service_credentials, vm1_launch_vm2): # Create a vm instance with the startup script
    image_response = compute.images().getFromFamily(
        project='ubuntu-os-cloud', family='ubuntu-2204-lts' # Use the Ubuntu 22.04lts disk image link
    ).execute()
    source_disk_image = image_response['selfLink']
    config = {
        'name': name,
        'machineType': f"zones/{zone}/machineTypes/e2-micro",  # Set machine size to f1-micro
        # Specify boot disk to use as source
        'disks': [ 
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': source_disk_image,  
                }
            }
        ],
        # Specify a network interface with NAT to access the public internet.
        'networkInterfaces': [{
            'network': f"global/networks/default",  # Attach to default VPC network
            'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}]
        }],
        # Metadata is readable from the instance and allows you to pass configuration from deployment scripts to instances.
        'metadata': {
            'items': [
                {
                    'key': 'startup-script',
                    'value': startup_script  # Put startup script in instance metadata for it to run automatically on boot
                },
                {
                    'key': 'vm2-startup-script',
                    'value': vm2_startup_script
                },
                {
                    'key': 'service-credentials',
                    'value': service_credentials
                },
                {
                    'key': 'vm1-launch-vm2-code',
                    'value': vm1_launch_vm2
                },
                {
                    'key': 'project',
                    'value': project
                },
            ]
        }
    }
    operation = compute.instances().insert(project=project, zone=zone, body=config).execute() # Execute API call to launch VM creation
    wait_for_operation(compute, project, zone, operation['name']) # wait for the operation to finish
    

def main():
    zone = 'us-west1-c'
    name = 'blog'

    with open('vm1-startup-script.sh') as f:
        vm1_startup_script = f.read()
    with open('vm2-startup-script.sh') as f:
        vm2_startup_script = f.read()
    with open('service-credentials.json') as f:
        service_credentials_json = f.read()
    with open('vm1-launch-vm2-code.py') as f:
        vm1_launch_vm2_code = f.read()

    
    create_instance(service, project, zone, name, vm1_startup_script, vm2_startup_script, service_credentials_json, vm1_launch_vm2_code)
    print("Your running instances are:")
    for instance in list_instances(service, project, zone):
        print(instance['name'])

if __name__ == '__main__':
       main()
