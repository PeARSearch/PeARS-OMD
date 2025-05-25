#!/usr/bin/env bash

printf "\n>>> Installing PeARS now <<<\n"

# Clone PeARS-OMD repository
printf "\nCloning the PeARS-OMD repository...\n"
git clone https://github.com/PeARSearch/PeARS-OMD.git

# Create virtual environment and install requirements
printf "\nCreating virtual environment...\n"
cd PeARS-OMD
virtualenv env && source env/bin/activate

printf "Installing requirements..."
pip install -r requirements.txt

# Set up authentification
printf "\nSetting up authentification...\n"
cd conf
cp pears.ini.template pears.ini

printf "\n####################\n"
printf "\nUSER INPUT REQUIRED.\nPlease write the authentification token found in your On My Disk client, under\n'Settings --> Device --> Use local PeARS server':\n"
read authtoken
printf "\n####################\n"

sed -i "s/AUTH_TOKEN=.*/AUTH_TOKEN=$authtoken/" pears.ini

# Set up Flask app keys
printf "\nSetting up the Flask app...\n"
session_cookie_name=`tr -dc A-Za-z0-9 </dev/urandom | head -c 20`
csrf_session_key=`tr -dc A-Za-z0-9 </dev/urandom | head -c 20`
secret_key=`tr -dc A-Za-z0-9 </dev/urandom | head -c 20`

sed -i "s/SESSION_COOKIE_NAME=.*/SESSION_COOKIE_NAME=$session_cookie_name/" pears.ini
sed -i "s/CSRF_SESSION_KEY=.*/CSRF_SESSION_KEY=$csrf_session_key/" pears.ini
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$secret_key/" pears.ini

printf "\n>>> PeARS has been installed successfully. <<<\n\nYou can run the app with:\n\ncd PeARS-OMD\nsource env/bin/activate\npython3 run.py.\n"
