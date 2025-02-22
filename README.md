# GuestDoor - Run Home Assistant automations from a local webpage using passcode authentication.

# DISCLAIMER: This project was developed with the assistance of ChatGPT. It is not intended for controlling critical security devices, as it has not been professionally verified.

This repository contains a Flask application running in a Docker container. Home Assistant (HA) authenticates with the APP using a rest command to store a passcode in the Postgres database. The application checks in the webpage if the entered passcode is correct, triggers a HA webhook if correct, or locks the IP after 3 failed attempts for 1 minute.

## Example usage

Need to trigger home assistant actions without the need of Home Assistant APP (i.e. guests) with the help of a wepbage-passcode authentication.
The address from the APP could be potentionally stored in a NFC tag.
When user within the WiFi network scans the NFC, a webpage launches and asks for a passcode, if the passcode is correct, a Home Assistant action is triggered.

## Features

- Trigger Automations without the Home Assistant APP, with a simple 4 digit passcode authentication.
- It can be used locally (if it isn't exposed to internet)
- Flask app running inside a Docker container.
- Environment variables to configure the app.
- Passcode stored and validated in a Postgres database.
- Home Assistant authentication through Bearer API_SECRET for storing passcode.
- Webhook trigger for automations.
- IP lockout after 3 failed attempts for 1 minute.

## Prerequisites

- Docker
- Docker Compose
- Home Assistant setup for webhook integration

## .env Configuration

The Flask app uses environment variables from a `.env` file. You need to configure the following variables:

```env
API_SECRET=your_api_secret           # Secret for Home Assistant authentication
HA_WEBHOOK=webhook_from_ha          # Webhook URL from Home Assistant
POSTGRES_USER=myuser                # PostgreSQL username
POSTGRES_PASSWORD=password          # PostgreSQL password
PORT=5000                            # Port for the Flask app to run
```

## Docker Setup

### 1. Create a local directory (i.e. GuestDoor):

```bash
mkdir GuestDoor
cd GuestDoor
```

### 2. Download docker-compose.yml from this repo:

```bash
wget https://raw.githubusercontent.com/Chreece/GuestDoor/main/docker-compose.yml
```

### 3. Create a .env file in the same directory with the following variables and change the values of them

```bash
API_SECRET=your_api_secret
HA_WEBHOOK=webhook_from_ha
POSTGRES_USER=myuser
POSTGRES_PASSWORD=password
PORT=5000
```
```
API_SECRET: A secret token for Authentication allowing HA to communicate with the APP and store the passcode.
HA_WEBHOOK: The webhook url that triggers your automation after the successful authentication.
POSTGRES_USER: Your PostgreSQL database user.
POSTGRES_PASSWORD: The password for the PostgreSQL database user.
PORT: The port that the webpage is listening
```

### 4. Build the Docker container:

```bash
docker compose up -d --build
```

The app will be accessible on `http://localhost:5000` (or the local IP from server and the port you specified).

## Home Assistant Setup

### 1. Create a rest command in your configuration.yaml:

```
rest_command:
  rest_passcode:
    url: "http://192.168.1.10:5000/add_passcode" # Change the ip:port with the ip and port from your flask app
    method: post
    headers:
      Authorization: !secret rest_passcode # This will be the authentication key for the app
      Content-Type: "application/json"
    payload: >
      {"passcode": {{ passcode }} }
```
### 2. Create a secret in your secrets.yaml:

```
rest_passcode: Bearer <here put the API_SECRET value from the .env file>
```

### 3. Create a webhook [trigger](https://www.home-assistant.io/docs/automation/trigger/#webhook-trigger) in Home Assistant:

This webhook will be called from the flask app if the access is granted (passcode check) and the automation will be triggered

### 4. Create an automation in Home Assistant to update the passcode:

Calling the following action to change the passcode:
```
action: rest_command.rest_passcode
data:
  passcode: <the new 4digit passcode>

```

## How It Works

- The app checks the passcode entered by the user against the one stored in the Postgres database.
- If the passcode is correct, it triggers the Home Assistant webhook defined in the `.env` file.
- If the passcode is incorrect, the user has 3 attempts. After 3 failed attempts, the IP will be locked for 1 minute.
- The lockout mechanism is based on IP, and after 1 minute, the IP can try again.

## Troubleshooting

- Ensure your `.env` file is correctly configured with the required variables.
- Make sure your Postgres database is running and accessible by the Flask app.
- If you're using Home Assistant, double-check the webhook URL and authentication details.

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE - see the [LICENSE](LICENSE) file for details.