#!/usr/bin/env python3
# I got a lot of the code from "https://github.com/googleapis/google-api-python-client/blob/main/samples/compute/create_instance.py"

import argparse
import os
import time
from pprint import pprint

import googleapiclient.discovery
import google.auth

credentials, project = google.auth.default()
service = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)

#
# Stub code - just lists all instances
#
def list_instances(compute, project, zone):
    result = compute.instances().list(project=project, zone=zone).execute()
    # return result['items'] if 'items' in result else None
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

def wait_for_global_operation(compute, project, operation):
    print("Waiting for operation to finish...")
    while True:
        result = compute.globalOperations().get(project=project, operation=operation).execute()

        if result["status"] == "DONE":
            print("done.")
            if "error" in result:
                raise Exception(result["error"])
            return result

        time.sleep(1)


def create_instance(compute, project, zone, name, startup_script): # Create a vm instance with the startup script
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
            'items': [{
                'key': 'startup-script',
                'value': startup_script  # Put startup script in instance metadata for it to run automatically on boot
            }]
        }
    }
    operation = compute.instances().insert(project=project, zone=zone, body=config).execute() # Execute API call to launch VM creation
    wait_for_operation(compute, project, zone, operation['name']) # wait for the operation to finish

def firewall_rule(compute, project):
    # Checks if the firewall already exists by retrieving all existing firewall rules in the project and evaluating if any existing rule matches 'allow-5000'
    rule_exists = False
    firewalls = compute.firewalls().list(project=project).execute().get('items', [])
    for rule in firewalls:
        if rule.get('name') == 'allow-5000':
            rule_exists = True
            break
    if rule_exists: # if it exists, can exit the function, if not, make the firewall rule
        print("Firewall rule 'allow-5000' already exists.")
        return
    firewall_body = {
        'name': 'allow-5000',                  # Rule name
        'allowed': [
            {
                'IPProtocol': 'tcp',             # Allow TCP protocol
                'ports': ['5000']                # Target port 5000 for Flask application
            }
        ],
        'sourceRanges': ['0.0.0.0/0'],          # Allow inbound traffic from any IP
        'targetTags': ['allow-5000']            # Target instances tagged with allow-5000
    }
    operation = compute.firewalls().insert(project=project, body=firewall_body).execute() # execute creating the firewall rule
    wait_for_global_operation(compute, project, operation['name'])

def network_tag(compute, project, zone, instance_name): # applies the network tag to the VM instance
    instance = compute.instances().get(project=project, zone=zone, instance=instance_name).execute()
    fingerprint = instance['tags']['fingerprint']
    
    existing_tags = instance['tags'].get('items', [])
    if 'allow-5000' not in existing_tags:
        existing_tags.append('allow-5000')

    tags_body = {
        'items': existing_tags,
        'fingerprint': fingerprint
    }
    # print(f"Applying network tag 'allow-5000' to '{instance_name}'...")
    operation = compute.instances().setTags(project=project, zone=zone, instance=instance_name, body=tags_body).execute()
    wait_for_operation(compute, project, zone, operation['name'])

def get_external_ip_address(compute, project, zone, instance_name): # Retrieve the VM's external IP address from the instance information returned by the Compute Engine API
    instance = compute.instances().get(project=project, zone=zone, instance=instance_name).execute()
    access_configs = instance['networkInterfaces'][0]['accessConfigs']
    for config in access_configs:
        if 'natIP' in config:
            return config['natIP']
    return None


def main():
    with open('startup-script.sh') as f:
           startup_script = f.read()

    zone = 'us-west1-c'
    name = 'blog'

    firewall_rule(service, project)
    create_instance(service, project, zone, name, startup_script)
    network_tag(service, project, zone, name)
    # wait_for_operation(compute, project, zone, operation["name"])

    print("Your running instances are:")
    for instance in list_instances(service, project, zone):
        print(instance['name'])

    ip = get_external_ip_address(service, project, zone, name)
    print("\nHere's the URL:")
    print(f"http://{ip}:5000")

if __name__ == '__main__':
       main()


   
    