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

def create_instance(compute, project, zone, name, startup_script): # Create a vm instance with the startup script
    image_response = compute.images().getFromFamily(
        project='ubuntu-os-cloud', family='ubuntu-2204-lts' # Use the Ubuntu 22.04lts disk image link
    ).execute()
    source_disk_image = image_response['selfLink']
    config = {
        'name': name,
        'machineType': f"zones/{zone}/machineTypes/e2-micro",  # Set machine size to f1-micro
        'tags': {'items': ['allow-5000']},
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

def get_external_ip_address(compute, project, zone, instance_name): # Retrieve the VM's external IP address from the instance information returned by the Compute Engine API
    instance = compute.instances().get(project=project, zone=zone, instance=instance_name).execute()
    access_configs = instance['networkInterfaces'][0]['accessConfigs']
    for config in access_configs:
        if 'natIP' in config:
            return config['natIP']
    return None

def main():
    with open('vm2-startup-script.sh') as f:
           startup_script = f.read()

    zone = 'us-west1-c'
    name = 'blog-vm2'

    create_instance(service, project, zone, name, startup_script)
    ip = get_external_ip_address(service, project, zone, name)
    print(f"\nVM-2 Flask app will be available at http://{ip}:5000") 
    print("(it'll take a while for it to work)\n")


if __name__ == '__main__':
    main()
