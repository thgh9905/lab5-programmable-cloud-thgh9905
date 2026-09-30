#!/usr/bin/env python3

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

def create_instance(compute, project, zone, name, snapshot_name): # Create a vm instance with the startup script
    # image_response = compute.images().getFromFamily(
    #     project='ubuntu-os-cloud', family='ubuntu-2204-lts' # Use the Ubuntu 22.04lts disk image link
    # ).execute()
    # source_disk_image = image_response['selfLink']
    config = {
        'name': name,
        'machineType': f"zones/{zone}/machineTypes/f1-micro",  # Set machine size to f1-micro
        # Specify boot disk to use as source
        'disks': [ 
            {
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceSnapshot': f'global/snapshots/{snapshot_name}',  
                }
            }
        ],
        # Specify a network interface with NAT to access the public internet.
        'networkInterfaces': [{
            'network': f"global/networks/default",  # Attach to default VPC network
            'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}]
        }],
        # Metadata is readable from the instance and allows you to pass configuration from deployment scripts to instances.
        # 'metadata': {
        #     'items': [{
        #         'key': 'startup-script',
        #         'value': startup_script  # Put startup script in instance metadata for it to run automatically on boot
        #     }]
        # }
    }
    operation = compute.instances().insert(project=project, zone=zone, body=config).execute() # Execute API call to launch VM creation
    wait_for_operation(compute, project, zone, operation['name']) # wait for the operation to finish

def create_snapshot(compute, project, zone, disk_name, snapshot_name):
    request_body = {'name': snapshot_name} 
    operation = compute.disks().createSnapshot(project=project, zone=zone, disk=disk_name, body=request_body).execute() # tell the disk to snapshot itself
    wait_for_operation(compute, project, zone, operation['name'])

def get_boot_disk_name(compute, project, zone, instance_name):
    instance = compute.instances().get(project=project, zone=zone, instance=instance_name).execute() # fetch an instance's full details for a single named resource
    for disk in instance['disks']: # finds and marks what disk the VM boots from
        if disk.get('boot'):
            return disk['source'].split('/')[-1]
    raise Exception(f"No boot disk found on instance {instance_name}")

def main():
    zone = 'us-west1-b'
    source_instance = 'blog'
    snapshot_name = f'base-snapshot-{source_instance}'
    disk_name = get_boot_disk_name(service, project, zone, source_instance)

    print(f"Boot disk is {disk_name}")

    print(f"Creating snapshot {snapshot_name}...")
    create_snapshot(service, project, zone, disk_name, snapshot_name)
    print("Snapshot created.")

    timings = []
    for i in range(1, 4):
        name = f'clone-{i}'
        start = time.time()
        create_instance(service, project, zone, name, snapshot_name)
        elapsed = time.time() - start # how long until the instance actually exists and is ready
        timings.append((name, elapsed)) # collects these results
        print(f"{name}: {elapsed:.2f} seconds")

    with open('TIMING.md', 'w') as f: # writes to TIMING.md
        f.write("# Instance creation timings\n")
        for name, elapsed in timings:
            f.write(f"- {name}: {elapsed:.2f} seconds\n")


if __name__ == '__main__':
       main()

# print("Your running instances are:")
# for instance in list_instances(service, project, 'us-west1-b'):
#     print(instance['name'])