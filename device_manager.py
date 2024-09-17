from netmiko import ConnectHandler, SSHDetect

class DeviceManager:
    def __init__(self, device_ip, device_type, credentials):
        self.device_ip = device_ip
        self.device_type = device_type
        self.credentials = credentials
        self.connection = None

    def connect(self):
        """Establishes a connection to the device using Netmiko."""
        # Handle autodetect case
        if self.device_type == "autodetect":
            # Use SSHDetect to find the device type
            remote_device = {
                "device_type": "autodetect",
                "host": self.device_ip,
                "username": self.credentials['username'],
                "password": self.credentials['password'],
                "secret": self.credentials.get('secret', '')
            }
            guesser = SSHDetect(**remote_device)
            self.device_type = guesser.autodetect()
            # print(f"Autodetected device type: {self.device_type}")
        
        # Proceed to connect using the detected or specified device type
        self.connection = ConnectHandler(
            device_type=self.device_type,
            host=self.device_ip,
            username=self.credentials['username'],
            password=self.credentials['password'],
            secret=self.credentials.get('secret', '')
        )
        self.connection.enable()

    def run_show_command(self, commands):
        """Executes the show commands on the device."""
        output = ""
        for command in commands:
            output += self.connection.send_command(command) + "\n"
        return output

    def disconnect(self):
        """Closes the connection to the device."""
        if self.connection:
            self.connection.disconnect()

