#!/usr/bin/env python3

"""
Copyright (c) 2019 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.0 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.

"""

import requests
import json
import re
from flask import Flask, render_template,request,flash,redirect,url_for
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__, static_folder="build/static", template_folder="build")

# Global variables
vlan_pools_list = []
domain_dict = {}
domaintoaep = []
aaeptopolicygroup = []
interface_policies = []
interface_selectors = []
interface_profiles = []
switch_profiles = []
# Change the below values as required
APIC_ip = "<ENTER_APIC_IP_HERE>"
APIC_username = "<ENTER_APIC_USERNAME_HERE>"
APIC_password = "<ENTER_APIC_PASSWORD_HERE>"


# Function to login
def login():
    try:
        url = "https://"+APIC_ip+"/api/aaaLogin.json"

        payload = "{\n  \"aaaUser\":{\n    \"attributes\":{\n      \"name\":\""+APIC_username+"\",\n      \"pwd\":\""+APIC_password+"\"\n    }\n  }\n}"

        #print("Payload: " + payload)

        response = requests.request("POST", url, data=payload, verify=False)

        print(response)

        token_dict = json.loads(response.text)
        get_token_dict = token_dict['imdata'].__getitem__(0)
        login_token = get_token_dict['aaaLogin']['attributes'].get('token')
    except Exception as e:
        print("Login failed with error - %s ",e)

    return login_token


token = login() # Login token


@app.route("/")
# Function to fetch vlan pool names
def get_vlan_pools():

    try:


        url = "https://"+APIC_ip+"/api/node/mo/uni/infra.json"

        querystring = {"query-target": "subtree", "target-subtree-class": "fvnsVlanInstP"}

        payload = ""
        headers = {
            "Cookie": "APIC-Cookie=" +token
        }

        response = requests.request("GET", url, data=payload, headers=headers, params=querystring, verify=False)
        vlan_pools_raw = json.loads(response.text)
        for i in range(vlan_pools_raw['imdata'].__len__()):
            name = vlan_pools_raw['imdata'][i]['fvnsVlanInstP']['attributes']['name']
            alloc = vlan_pools_raw['imdata'][i]['fvnsVlanInstP']['attributes']['allocMode']
            dn = "[" + name + "]-" + alloc
            vlan_pools_list.append(dn)
    except Exception as e:
        print("Failed to fetch Vlan pool list - %s",e)
    return render_template('index.html', vlan_pool=vlan_pools_list)

# Function to get domain names
def get_domain_per_vlan_pool(vlan_pool_name):
    vlan_pool = vlan_pool_name
    url = "https://"+APIC_ip+"/api/node/mo/uni.json?target-subtree-class=infraRsVlanNs&query-target=subtree"

    payload = ""
    headers = {
        "Cookie": "APIC-Cookie=" + token,
        'cache-control': "no-cache"
    }

    response = requests.request("GET", url, data=payload, headers=headers, verify=False)
    dom_raw = json.loads(response.text)
    for i in range(dom_raw['imdata'].__len__()):
        if dom_raw['imdata'][i]['infraRsVlanNs']['attributes']['tDn'] == 'uni/infra/vlanns-' + vlan_pool:
            domain_dict.setdefault(vlan_pool,[])
            domain_dict[vlan_pool].append(dom_raw['imdata'][i]['infraRsVlanNs']['attributes']['dn'])
    return domain_dict


# Function to get AAEP names
def get_aaep_names(dom_name):
    url = "https://"+APIC_ip+"/api/node/mo/uni.json?query-target=subtree&target-subtree-class=infraRtDomP"

    headers = {"Cookie": "APIC-Cookie=" + token}

    response = requests.request("GET", url, headers=headers, verify=False)
    r = response.json()
    lst = domain_dict.get(dom_name)
    for i in r["imdata"]:
        for j in lst.__iter__():
            x = re.findall(j.rstrip("rsvlanNs") + "*", i["infraRtDomP"]["attributes"]["dn"])
            if (x):
                z=i["infraRtDomP"]["attributes"]["dn"].split("/")[-1]
                domaintoaep.append({j:z.split("-",1)[1].split("]")[0]})
    return domaintoaep


# Function to get policy groups
def get_policy_groups(aepname):
    domainName = domain_dict
    url = "https://"+APIC_ip+"/api/node/mo/uni/infra/attentp-"+aepname+".json?query-target=children&target-subtree-class=infraRtAttEntP"
    headers = {"Cookie": "APIC-Cookie=" + token}
    response = requests.request("GET", url, headers=headers, verify=False)
    r = response.json()
    for j in r["imdata"].__iter__():
        aaeptopolicygroup.append({aepname:j["infraRtAttEntP"]["attributes"]["tDn"].split("/")[3]})
    return aaeptopolicygroup


# Function to get interface policies
def get_interface_policies(port_group):
    policy_list = []
    url = "https://"+APIC_ip+"/api/node/mo/uni/infra/funcprof/"+port_group+".json?query-target=children"
    headers = {"Cookie": "APIC-Cookie=" + token}
    response = requests.request("GET", url, headers=headers, verify=False)
    r = response.json()
    for j in r["imdata"].__iter__():
        for i in j.__iter__():
            x = j[i]["attributes"]["tCl"]
            x = "%s%s" % (x[0].upper(), x[1:])
            if (j[i]["attributes"].get("tn" + x + "Name")):
                policy_list.append(j[i]["attributes"].get("tn" + x + "Name"))
    interface_policies.append({port_group:policy_list})
    return interface_policies


# Function to get leaf interface selectors and profiles
def get_interface_selectors_and_profiles():
    query_dn_list = []
    url = "https://"+APIC_ip+"/api/node/mo/uni/infra.json?query-target-filter=not(wcard(infraAccPortP.dn,%22__ui_%22))&query-target=subtree&target-subtree-class=infraAccPortP&query-target=subtree&target-subtree-class=infraHPortS,infraRsAccBaseGrp"
    headers = {"Cookie": "APIC-Cookie=" + token}
    response = requests.request("GET", url, headers=headers, verify=False)
    r = response.json()
    # Mapping interface selectors and leaf interface profile
    for i in r["imdata"].__iter__():
        for k in i.__iter__():
            if (k == "infraHPortS"):
                query_dn = i[k]["attributes"]["dn"]
                query_dn_list.append(query_dn)
                leaf_int_profile = query_dn.split("/").pop(2)
                port = i[k]["attributes"]["name"]
                interface_profiles.append({port:leaf_int_profile})
    # Mapping policy group and interface selectors
    for t in r["imdata"].__iter__():
        for u in t.__iter__():
            if (u == "infraRsAccBaseGrp"):
                for interface in query_dn_list.__iter__():
                    if (t[u]["attributes"]["dn"] == interface + "/rsaccBaseGrp"):
                        port_full = t[u]["attributes"]["dn"].split("/").pop(3)
                        port = port_full.split("-").pop(1)
                        policy_grp = t[u]["attributes"]["tDn"].split("/").pop(3)
                        interface_selectors.append({policy_grp:port})
    return


# Function to get leaf switch profiles
def get_leaf_switch_profile():
    url = "https://"+APIC_ip+"/api/node/mo/uni/infra.json?query-target=subtree&target-subtree-class=infraNodeP&query-target-filter=not(wcard(infraNodeP.dn,%22__ui_%22))&target-subtree-class=infraRsAccPortP&query-target=subtree"
    headers = {"Cookie": "APIC-Cookie=" + token}
    response = requests.request("GET", url, headers=headers, verify=False)
    r = response.json()
    for i in r["imdata"].__iter__():
        for j in i.__iter__():
            if (j == "infraRsAccPortP"):
                switch_profiles.append({i[j]["attributes"]["tDn"].split("/")[2]:i[j]["attributes"]["dn"].split("/")[2]})
    return switch_profiles


# Function to generate graph
@app.route("/gengraph", methods=['POST'])
def generate_graph():
    try:
        vlan_pool = vlan_pools_list
        pool_name = request.form['select-vlan-pool']
        g = get_domain_per_vlan_pool(pool_name)
        get_aaep_names(pool_name)
        k = domaintoaep
        unique_aep = set(val for dic in k for val in dic.values())
        graph_data = {"nodeDataArray": [], "linkDataArray": []}
        graph_data["nodeDataArray"].append({"key": pool_name, "color": "lightblue", "comment": "Vlan Pool"})
        for i in g[pool_name]:
            # Domain and Vlan Pool mapping
            graph_data["nodeDataArray"].append({"key": i, "color": "orange", "comment": "Domains"})
            graph_data["linkDataArray"].append({"from": pool_name, "to": i})
        for u_aep in unique_aep:
            graph_data["nodeDataArray"].append({"key": u_aep, "color": "pink", "comment": "AEP"})
        for dom in k.__iter__():
            for j, l in dom.items():
                graph_data["linkDataArray"].append({"from": j, "to": l})

        # Aep to port group
        for aeps in unique_aep:
            get_policy_groups(aeps)
        unique_port_group = set(val for dic in aaeptopolicygroup for val in dic.values())
        for u_pg in unique_port_group:
            graph_data["nodeDataArray"].append({"key": u_pg, "color": "lightgreen", "comment": "Interface Policy Group"})
        for pg in aaeptopolicygroup.__iter__():
            for pg_k, pg_v in pg.items():
                graph_data["linkDataArray"].append({"from": pg_k, "to": pg_v})

        # interface Policies
        for u in unique_port_group:
            get_interface_policies(u)
        unique_policies = []
        for dic in interface_policies:
            for val in dic.values():
                if (val not in unique_policies.__iter__() and val != []):
                    unique_policies.append(val)
        for u in unique_policies:
            graph_data["nodeDataArray"].append({"key": ','.join(u), "color": "brown", "comment": "Interface Policies"})
        for int_policy in interface_policies.__iter__():
            for int_policy_k, int_policy_v in int_policy.items():
                graph_data["linkDataArray"].append({"from": ','.join(int_policy_v), "to": int_policy_k})

        # Interface Selectors
        get_interface_selectors_and_profiles()
        unique_interface_selectors = set(
            val for dic in interface_selectors for i in unique_port_group if (i in dic.keys()) for val in dic.values())
        for intf_sel in unique_interface_selectors:
            graph_data["nodeDataArray"].append({"key": intf_sel, "color": "deepskyblue", "comment": "Interface Selectors"})
        for int_sel in interface_selectors.__iter__():
            for int_sel_k, int_sel_v in int_sel.items():
                graph_data["linkDataArray"].append({"from": int_sel_k, "to": int_sel_v})

        # Leaf interface profiles
        unique_interface_profiles = set(
            val for dic in interface_profiles for i in unique_interface_selectors if (i in dic.keys()) for val in
            dic.values())
        for intf_prof in unique_interface_profiles:
            graph_data["nodeDataArray"].append(
                {"key": intf_prof, "color": "lightsalmon", "comment": "Leaf Interface Profile"})
        for int_prof in interface_profiles.__iter__():
            for int_prof_k, int_prof_v in int_prof.items():
                graph_data["linkDataArray"].append({"from": int_prof_k, "to": int_prof_v})

        # Leaf switch profile
        get_leaf_switch_profile()
        unique_switch_profile = set(
            val for dic in switch_profiles for i in unique_interface_profiles if (i in dic.keys()) for val in dic.values())
        for swtch_profile in unique_switch_profile:
            graph_data["nodeDataArray"].append(
                {"key": swtch_profile, "color": "turquoise", "comment": "Leaf Switch Profile"})
        for switch_prof in switch_profiles.__iter__():
            for switch_prof_k, switch_prof_v in switch_prof.items():
                graph_data["linkDataArray"].append({"from": switch_prof_k, "to": switch_prof_v})
    except Exception as e:
        print("Error", e)
    return render_template('index.html',data=json.dumps(graph_data), vlan_pool = vlan_pool)

app.run(host='0.0.0.0',port=5001)
