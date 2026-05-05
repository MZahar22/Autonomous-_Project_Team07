import rclpy
from rclpy.node import Node
import serial
import sys, select, termios, tty

# Key mappings
settings = termios.tcgetattr(sys.stdin)

msg = """
Reading from keyboard, P-Controller running on Arduino!
---------------------------
Up/Down: Accelerate/Reverse (Target RPM)
Left/Right: Steer
Space: Force Stop
CTRL-C to quit
"""

class TeleopNode(Node):
    def __init__(self):
        super().__init__('teleop_hardware_node')
        
        self.arduino_port = '/dev/ttyACM0'
        self.baud_rate = 115200
        try:
            self.ser = serial.Serial(self.arduino_port, self.baud_rate, timeout=0.01) # Faster timeout for 20ms loop
            self.get_logger().info('Serial connection established.')
        except serial.SerialException:
            self.get_logger().error('Could not open serial port. Check connection!')
            sys.exit(1)
            
        self.target_rpm = 0
        self.steering = 90 

    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        select.select([sys.stdin], [], [], 0.02) # Faster key polling to match 20ms data
        key = sys.stdin.read(1)
        if key == '\x1b':
            key += sys.stdin.read(2)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        return key

    def run(self):
        print(msg)
        try:
            while rclpy.ok():
                key = self.get_key()
                
                # Up Arrow - Increase Target RPM by 10 (Max is now 250)
                if key == '\x1b[A':
                    self.target_rpm = min(self.target_rpm + 10, 250)
                # Down Arrow - Decrease Target RPM by 10 (Min is now -250)
                elif key == '\x1b[B':
                    self.target_rpm = max(self.target_rpm - 10, -250)
                # Right Arrow - Steer Right
                elif key == '\x1b[D':
                    self.steering = max(self.steering - 15, 55) 
                # Left Arrow - Steer Left
                elif key == '\x1b[C':
                    self.steering = min(self.steering + 15, 125)
                # Spacebar (Brake)
                elif key == ' ':
                    self.target_rpm = 0
                    self.steering = 90
                # CTRL-C
                elif key == '\x03':
                    break

                # Format and send the Target RPM command to the Arduino
                if key != '':
                    command = f"{self.target_rpm},{self.steering}\n"
                    self.ser.write(command.encode('utf-8'))

                # Receive Actual RPM from the Arduino for verification
                while self.ser.in_waiting > 0:
                    try:
                        incoming_data = self.ser.readline().decode('utf-8').strip()
                        
                        if incoming_data.startswith("RPM:"):
                            actual_rpm = float(incoming_data.split(":")[1])
                            self.get_logger().info(f'Target: {self.target_rpm} RPM | Actual: {actual_rpm:.2f} RPM')
                            
                    except Exception as e:
                        pass

        finally:
            self.ser.write(b"0,90\n")
            self.ser.close()

def main(args=None):
    rclpy.init(args=args)
    node = TeleopNode()
    node.run()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()