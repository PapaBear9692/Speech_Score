````md
# Production Deployment Guide (Python App) Gunicorn + Nginx on Ubuntu (User: erpsoft)
 



## Part 1 : Getting the app and server ready
### Login Into Server
```bash
ssh user@ip -p port
````

### Install required packages (apps)
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install python3 python3-venv git nginx gunicorn
```

### Clone the app from github (repo must be public, if private add github ssh key to the system first)
```bash
git clone https://github.com/PapaBear9692/Speech_Score.git
```

### Switch to app folder
```bash
cd Speech_Score
```

### Create and activate environment. Then install requirements file
```bash
python3 -m venv .spvenv
source .spvenv/bin/activate
pip install -r requirements.txt
pip install gunicorn // If already not in requirements.txt
```

### Test if app the runs
```bash
python3 app.py
```
**solve any issues if app does no run

### Try serving the app using gunicorn
```bash
gunicorn -w 3 -b 0.0.0.0:8000 app:app
```


## Part 2 : Deploying the app
### Switch to superuser
```bash
su
```

### Make a service to run the app continuously in backgoroun 
```bash
nano /etc/systemd/system/speech_score.service
```

### Paste this service config
**Here 8000 is the port number, -w 3 means 3 workers for the app (3 instance at a time if needed)

```ini
[Unit]
Description=Speech Score Web Application Service
After=network.target

[Service]
User=erpsoft
Group=erpsoft
WorkingDirectory=/home/erpsoft/Speech_Score
Environment="PATH=/home/erpsoft/Speech_Score/.spvenv/bin"
ExecStart=/home/erpsoft/Speech_Score/.spvenv/bin/gunicorn -w 3 -b 127.0.0.1:8000 app:app

Restart=always

[Install]
WantedBy=multi-user.target
```


### Enable and start the service
```bash
systemctl daemon-reload   // reloads the service list
systemctl enable speech_score    // enable the service (turn on auto start)
systemctl start speech_score    // start the service right now
systemctl status speech_score    // check status of the service (check is the service is running)
```

### Only If service not running
```bash
journalctl -u speech_score-f    // shows service log
```


### Create nginx config for the app
```bash
nano /etc/nginx/sites-available/speech_score
```


### Paste this nginx config 
**This is just basic config, can do more advance things like https only, multiple instance, load balancing etc

```nginx
server {
    listen 80;
    server_name server_ip/web_address;

    location / {
        proxy_pass http://127.0.0.1:8000; // this port number must match the port number used in service

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```


Or use this advanced config to deploy in a route instead
```
location /speech/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /speech;
    proxy_set_header X-Forwarded-Host $host;

    proxy_redirect off;
    proxy_buffering off;

    client_max_body_size 20M;
    proxy_read_timeout 300;
    proxy_connect_timeout 300;
    proxy_send_timeout 300;
}
```
### Link the sites-available config sites-enabled file
```bash
ln -s /etc/nginx/sites-available/speech_score /etc/nginx/sites-enabled/speech_score
nginx -t        // test if nginx config is valid, if not, recheck
systemctl restart nginx    // restart nginx (nginx also runs as a service to stay in backgorund and auto restart)
```

### Restart the services one last time
```bash
systemctl restart speech_score
systemctl status speech_score
systemctl restart nginx
```


DONE 🚀
Now the app should be visible from devices connected to the internal network.
Check at : server_ip:8000 
