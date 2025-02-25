#!/usr/bin/python

# FUJITSU LIMITED
# Copyright 2018 FUJITSU LIMITED
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division)
__metaclass__ = type


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}


DOCUMENTATION = '''
---
module: irmc_eventlog

short_description: handle iRMC eventlogs

description:
    - Ansible module to handle iRMC eventlogs via Restful API.
    - Module Version V1.2.

requirements:
    - The module needs to run locally.
    - iRMC S4 needs FW >= 9.04, iRMC S5 needs FW >= 1.25.
    - Python >= 2.6
    - Python modules 'future', 'requests', 'urllib3'

version_added: "2.4"

author:
    - Nakamura Takayuki (@nakamura-taka)

options:
    irmc_url:
        description: IP address of the iRMC to be requested for data.
        required:    true
    irmc_username:
        description: iRMC user for basic authentication.
        required:    true
    irmc_password:
        description: Password for iRMC user for basic authentication.
        required:    true
    validate_certs:
        description: Evaluate SSL certificate (set to false for self-signed certificate).
        required:    false
        default:     true
    command:
        description: Handle iRMC eventlogs.
        required:    false
        default:     list
        choices:     ['list', 'get', 'clear']
    eventlog_type:
        description: Specific eventlog to handle.
        default:     SystemEventLog
        required:    false
        choices:     ['SystemEventLog', 'InternalEventLog']
    id:
        description: Specific eventlog ID to get.
        required:    false

notes:
    - See http://manuals.ts.fujitsu.com/file/13371/irmc-restful-spec-en.pdf
    - See http://manuals.ts.fujitsu.com/file/13372/irmc-redfish-wp-en.pdf
'''

EXAMPLES = '''
# List iRMC InternalEventLog
- name: List iRMC InternalEventLog
  irmc_eventlog:
    irmc_url: "{{ inventory_hostname }}"
    irmc_username: "{{ irmc_user }}"
    irmc_password: "{{ irmc_password }}"
    validate_certs: "{{ validate_certificate }}"
    command: "list"
    eventlog_type: "InternalEventLog"
  delegate_to: localhost

# Get specific SystemEventLog entry information
- name: Get specific SystemEventLog entry information
  irmc_eventlog:
    irmc_url: "{{ inventory_hostname }}"
    irmc_username: "{{ irmc_user }}"
    irmc_password: "{{ irmc_password }}"
    validate_certs: "{{ validate_certificate }}"
    command: "get"
    id: 0
  delegate_to: localhost
'''

RETURN = '''
# eventlog_entry data returned for command "get":
    AlertGroup:
        description: group which caused the event
        returned: always
        type: string
        sample: Memory
    Cause:
        description: reason for the event if available
        returned: always
        type: string
        sample: The memory module was not approved and released for this system by the system manufacturer
    Created:
        description: dated of the event
        returned: always
        type: string
        sample: "2018-07-24T15:57:40+02:00"
    EventSource:
        description: where the event originated from
        returned: always
        type: string
        sample: iRMC S5
    Id:
        description: event ID
        returned: always
        type: int
        sample: 20
    Message:
        description: event entry text
        returned: always
        type: string
        sample: DIMM-1E Non Fujitsu Memory Module detected - Warranty restricted!
    Resolutions:
        description: list of possible solitions for the problem, if available
        returned: always
        type: list
        sample:
    Severity:
        description: serverity of event
        returned: always
        type: string
        sample: Warning
    Type:
        description: event type
        returned: always
        type: string
        sample: SEL

# eventlog data returned for command "list":
    List of individual eventlog_entries (see above):

# For all other commands:
    Default return values:
'''


from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fujitsu.ansible.plugins.module_utils.irmc import irmc_redfish_get, irmc_redfish_post, get_irmc_json


# Global
result = dict()


def irmc_eventlog(module):
    # initialize result
    result['changed'] = False
    result['status'] = 0

    if module.check_mode:
        result['msg'] = "module was not run"
        module.exit_json(**result)

    # preliminary parameter check
    if module.params['command'] == "get" and module.params['id'] is None:
        result['msg'] = "Command 'get' requires 'id' parameter to be set!"
        result['status'] = 10
        module.fail_json(**result)

    if module.params['command'] == "list":
        status, data, msg = irmc_redfish_get(module, "redfish/v1/Managers/iRMC/LogServices/{0}/Entries".
                                             format(module.params['eventlog_type']))
        if status < 100:
            module.fail_json(msg=msg, status=status, exception=data)
        elif status not in (200, 202, 204):
            module.fail_json(msg=msg, status=status)

        eventlogs = get_irmc_json(data.json(), ["Members"])
        result['eventlog'] = []
        for item in eventlogs:
            result['eventlog'].append(get_irmc_eventlog_info(module, item))
    elif module.params['command'] == "clear":
        url = "redfish/v1/Managers/iRMC/LogServices/{0}/Actions/LogService.ClearLog". \
              format(module.params['eventlog_type'])
        status, data, msg = irmc_redfish_post(module, url, "")
        if status < 100:
            module.fail_json(msg=msg, status=status, exception=data)
        elif status not in (200, 202, 204):
            module.fail_json(msg=msg, status=status)
        result['changed'] = True
    else:
        status, data, msg = irmc_redfish_get(module, "redfish/v1/Managers/iRMC/LogServices/{0}/Entries/{1}".
                                             format(module.params['eventlog_type'], module.params['id']))
        if status < 100:
            module.fail_json(msg=msg, status=status, exception=data)
        elif status not in (200, 202, 204):
            module.fail_json(msg=msg, status=status)

        result['eventlog_entry'] = get_irmc_eventlog_info(module, data.json())

    module.exit_json(**result)


def get_irmc_eventlog_info(module, item):
    eventlog = {}
    eventlog['Id'] = item['Id']
    eventlog['Severity'] = item['Severity']
    eventlog['Created'] = item['Created']
    eventlog['Type'] = item['EntryType']
    eventlog['AlertGroup'] = get_irmc_json(item, ["Oem", "ts_fujitsu", "AlertGroup"])
    if module.params['eventlog_type'] == "SystemEventLog":
        eventlog['EventSource'] = get_irmc_json(item, ["Oem", "ts_fujitsu", "EventSource"])
        eventlog['Message'] = get_irmc_json(item, ["Oem", "ts_fujitsu", "MessageOEM", "en"])[0]
        if get_irmc_json(item, ["Oem", "ts_fujitsu", "Cause"]) is not None:
            eventlog['Cause'] = get_irmc_json(item, ["Oem", "ts_fujitsu", "Cause", "en"])[0]
        else:
            eventlog['Cause'] = None
        if get_irmc_json(item, ["Oem", "ts_fujitsu", "Resolutions"]) is not None:
            eventlog['Resolutions'] = get_irmc_json(item, ["Oem", "ts_fujitsu", "Resolutions", "en"])[0]
        else:
            eventlog['Resolutions'] = None
    else:
        eventlog['MessageId'] = item['MessageId']
        eventlog['Message'] = item['Message']
    return eventlog


def main():
    # import pdb; pdb.set_trace()
    module_args = dict(
        irmc_url=dict(required=True, type="str"),
        irmc_username=dict(required=True, type="str"),
        irmc_password=dict(required=True, type="str", no_log=True),
        validate_certs=dict(required=False, type="bool", default=True),
        command=dict(required=False, type="str", default="list",
                     choices=['list', 'get', 'clear']),
        eventlog_type=dict(required=False, type="str", default="SystemEventLog",
                           choices=["SystemEventLog", "InternalEventLog"]),
        id=dict(required=False, type="int")
    )
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    irmc_eventlog(module)


if __name__ == '__main__':
    main()
