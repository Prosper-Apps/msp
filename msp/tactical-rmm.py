import frappe
from frappe.utils.password import get_decrypted_password

import requests
import json
from pprint import pprint
import re
from .tools import render_card_html, render_single_card

@frappe.whitelist()
def get_agents(it_landscape, rmm_instance = None, tactical_rmm_tenant_caption = None):
    pass
                            

@frappe.whitelist()
def get_relevant_software_for_agent(agent_id):
    found_software = []
    software_for_agent = get_software_for_agent(agent_id)
    if "software" in software_for_agent:
        for s in software_for_agent["software"]:
            result = _match_software(s)
            if result:
                found_software.append(result)

    return(found_software)

def _match_software(rmm_software_elememt):
    sw_match_list = frappe.get_all("IT Software Matching", fields=["search_regex", "software_name", "category"], filters={"active": 1})
    for el in sw_match_list:
        result = re.match(el["search_regex"])
        if result:
            return {el["software_name"], el["category"]}
    return None

@frappe.whitelist()
def search_office(agents = None):
    points_for_found_strings = {}
    agents_with_office = []

    if not agents:
        agents = get_all_agents()
    todo = len(agents)
    count = 0
    for agent in agents:
        found_office = False
        count = count + 1
        print("verarbeite agent " + str(count) + " von " + str(todo))
        software_for_agent = get_software_for_agent(agent["agent_id"])
        if "software" in software_for_agent:
            for s in software_for_agent["software"]:
                if (s["name"].lower().startswith("Microsoft Office".lower())):
                    found_string = s["name"]
                    found_office = True
                    
                    if found_string in points_for_found_strings.keys():
                        points_for_found_strings[found_string] = points_for_found_strings[found_string] + 1
                    else:
                        points_for_found_strings[found_string] = 1
            if found_office:
                agents_with_office.append(agent)
        else:
            pass
       


    print(points_for_found_strings)
    #print(len(agents_with_office))
    search_for_office_patches(agents_with_office)
    print(points_for_found_strings)

def search_for_office_patches(agents_with_office):
    count = 0
    for agent in agents_with_office:
        found_patches_for_office = False
        patches = get_patches_for_agent(agent["agent_id"])
        for patch in patches:
            if "office".lower() in patch["title"].lower():
                found_patches_for_office = True
        if found_patches_for_office == False:
            print("kein patch für agent mit office gefunden: " + agent["hostname"] + " | " + agent["client_name"])
            count = count + 1
    print("Anzahl Clients: " + str(count))
    



@frappe.whitelist()
def get_agents_pretty(documentation):
    documentation_doc = frappe.get_doc("MSP Documentation", documentation)

    if not documentation_doc.tactical_rmm_tenant_caption:
        frappe.throw("Tenant Caption missing")

    client_name = documentation_doc.tactical_rmm_tenant_caption
    site_name = documentation_doc.tactical_rmm_site_name
    agents = get_all_agents()
    
    # Filter and organize agents
    agent_list = []
    for agent in agents:
        # Filter by client_name and optionally by site_name if provided
        if agent["client_name"] == client_name and (not site_name or agent["site_name"] == site_name):
            # Format agent data for card rendering
            agent_item = {
                'title': agent['hostname'],  # Using hostname as title
                'type': agent['monitoring_type'],  # workstation/server
                'ip': agent['local_ips'],
                'location': agent['site_name'],
                'metadata': {
                    'Operating System': agent['operating_system'],
                    'Hardware Model': render_model(agent['make_model']),
                    'Serial Number': agent.get('serial_number', ''),
                    'CPU': ", ".join(agent['cpu_model']) if isinstance(agent['cpu_model'], list) else agent['cpu_model'],
                    'Graphics': agent['graphics'],
                    'Storage': ", ".join(agent['physical_disks']) if isinstance(agent['physical_disks'], list) else agent['physical_disks'],
                    'Public IP': agent['public_ip'],
                    'Last Seen': agent['last_seen'],
                    'Last User': agent['logged_username']
                },
                'description': agent.get('description', '')
            }
            agent_list.append(agent_item)

    # Check if any agents were found
    if not agent_list:
        no_agents_message = f"<div class='alert alert-warning'>No agents found for client '{client_name}'"
        if site_name:
            no_agents_message += f" at site '{site_name}'"
        no_agents_message += ".</div>"
        
        # Update the documentation with the message
        documentation_doc.system_list = no_agents_message
        documentation_doc.workstation_list = no_agents_message
        documentation_doc.server_list = no_agents_message
        documentation_doc.save()
        
        return []

    # Generate HTML using the shared render_card_html function from tools.py
    all_agents_html = render_card_html(agent_list, "tactical")
    
    # Filter lists for workstations and servers
    workstation_list = [a for a in agent_list if a['type'].lower() == 'workstation']
    server_list = [a for a in agent_list if a['type'].lower() == 'server']
    
    # Generate separate HTML for workstations and servers
    workstation_html = render_card_html(workstation_list, "tactical")
    server_html = render_card_html(server_list, "tactical")

    # Update the documentation
    documentation_doc.system_list = all_agents_html
    documentation_doc.workstation_list = workstation_html
    documentation_doc.server_list = server_html
    documentation_doc.save()
    
    return agent_list


def get_all_agents():
    settings = frappe.get_single("MSP Settings")
    if not settings.api_key:
        frappe.throw("API Key is missing")
    if not settings.api_url:
        frappe.throw("API URL is missing")
    
    API = settings.api_url
    HEADERS = {
        "Content-Type": "application/json",
        "X-API-KEY": get_decrypted_password("MSP Settings", "MSP Settings", "api_key", raise_exception=True),
    }

    agents = requests.get(f"{API}/agents/?detail=true", headers=HEADERS)
    return agents.json()

def get_software_for_agent(agent_id=None):
    settings = frappe.get_single("MSP Settings")
    if not settings.api_key:
        frappe.throw("API Key is missing")
    if not settings.api_url:
        frappe.throw("API URL is missing")
    
    API = settings.api_url
    HEADERS = {
        "Content-Type": "application/json",
        "X-API-KEY": get_decrypted_password("MSP Settings", "MSP Settings", "api_key", raise_exception=True),
    }

    if not agent_id:
        frappe.throw("Agent ID fehlt")

    software_for_agent = requests.get(f"{API}/software/{agent_id}/", headers=HEADERS)
    return software_for_agent.json()

def get_patches_for_agent(agent_id=None):
    settings = frappe.get_single("MSP Settings")
    if not settings.api_key:
        frappe.throw("API Key is missing")
    if not settings.api_url:
        frappe.throw("API URL is missing")
    
    API = settings.api_url
    HEADERS = {
        "Content-Type": "application/json",
        "X-API-KEY": get_decrypted_password("MSP Settings", "MSP Settings", "api_key", raise_exception=True),
    }

    if not agent_id:
        frappe.throw("Agent ID fehlt")

    patches_for_agent = requests.get(f"{API}/winupdate/{agent_id}/", headers=HEADERS)
    return patches_for_agent.json()




def make_agent_md_output(agents):
    # Prepare items for card rendering
    items = []
    for agent in agents:
        items.append({
            'title': agent['hostname'],
            'type': agent['monitoring_type'],
            'ip': agent['local_ips'],
            'location': agent['site_name'],
            'status': agent['status'],
            'metadata': {
                'OS': agent['operating_system'],
                'CPU': ", ".join(agent['cpu_model']) if isinstance(agent['cpu_model'], list) else agent['cpu_model'],
                'GPU': agent['graphics'],
                'Disks': ", ".join(agent['physical_disks']) if isinstance(agent['physical_disks'], list) else agent['physical_disks'],
                'Model': render_model(agent['make_model']),
                'Serial Number': agent.get('serial_number'),
                'Type': agent['monitoring_type'],
                'Site': agent['site_name'],
                'Public IP': agent['public_ip'],
                'Last Seen': agent['last_seen'],
                'Last User': agent['logged_username']
            },
            'description': agent.get('description')
        })

    return render_card_html(items, "agent")


def render_model(model):
    if model == "System manufacturer System Product Name":
        return "not specified"
    if model == "Xen HVM domU":
        return "Virtual Mashine running on Xen Hypervisor"
    return model



""" 
{'agent_id': 'mXXJYhUHwrMPcAAuvsmGMFhcVsjWVMQqHKaVCfBN',
23:31:32 web.1            |  'alert_template': None,
23:31:32 web.1            |  'block_policy_inheritance': False,
23:31:32 web.1            |  'boot_time': 1675142998.0,
23:31:32 web.1            |  'checks': {'failing': 0,
23:31:32 web.1            |             'has_failing_checks': False,
23:31:32 web.1            |             'info': 0,
23:31:32 web.1            |             'passing': 0,
23:31:32 web.1            |             'total': 0,
23:31:32 web.1            |             'warning': 0},
23:31:32 web.1            |  'client_name': 'Cohrs Werkstaetten',
23:31:32 web.1            |  'cpu_model': ['Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz'],
23:31:32 web.1            |  'description': '',
23:31:32 web.1            |  'goarch': 'amd64',
23:31:32 web.1            |  'graphics': 'NVIDIA Quadro K2000D',
23:31:32 web.1            |  'has_patches_pending': False,
23:31:32 web.1            |  'hostname': 'CWWS13',
23:31:32 web.1            |  'italic': False,
23:31:32 web.1            |  'last_seen': '2023-01-31T14:34:41.479173Z',
23:31:32 web.1            |  'local_ips': '192.168.24.161',
23:31:32 web.1            |  'logged_username': 'o.ruschmeyer',
23:31:32 web.1            |  'maintenance_mode': False,
23:31:32 web.1            |  'make_model': 'System manufacturer System Product Name',
23:31:32 web.1            |  'monitoring_type': 'workstation',
23:31:32 web.1            |  'needs_reboot': False,
23:31:32 web.1            |  'operating_system': 'Windows 10 Pro, 64 bit v22H2 (build 19045.2486)',
23:31:32 web.1            |  'overdue_dashboard_alert': False,
23:31:32 web.1            |  'overdue_email_alert': False,
23:31:32 web.1            |  'overdue_text_alert': False,
23:31:32 web.1            |  'pending_actions_count': 0,
23:31:32 web.1            |  'physical_disks': ['Kingston SHPM2280P2/240G 224GB IDE'],
23:31:32 web.1            |  'plat': 'windows',
23:31:32 web.1            |  'public_ip': '90.187.0.65',
23:31:32 web.1            |  'site_name': 'Fallingbostel',
23:31:32 web.1            |  'status': 'overdue',
23:31:32 web.1            |  'version': '2.4.4'} """