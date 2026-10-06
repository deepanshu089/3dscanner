#!/usr/bin/env python3
"""
MD10C Actuator Control with Integrated Camera Capture
Combines linear actuator movement with synchronized image capture
"""

import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
from datetime import datetime
from libcamera import Transform
import os

# ============================================
# GPIO Configuration for MD10C Actuator
# ============================================
DIR_PIN = 17    # Direction control pin
PWM_PIN = 18    # PWM control pin (hardware PWM)

GPIO.setmode(GPIO.BCM)
GPIO.setup(DIR_PIN, GPIO.OUT)
GPIO.setup(PWM_PIN, GPIO.OUT)

# Initialize PWM at 1 kHz
pwm = GPIO.PWM(PWM_PIN, 1000)
pwm.start(0)  # Start with 0% duty cycle (stopped)

# ============================================
# NEW: Physical Limit Switch Configuration
# ============================================
# Change these pins if your limit switches are connected
# to different GPIO pins.

UP_LIMIT_PIN = 22
DOWN_LIMIT_PIN = 23

# Limit switches assumed:
# GPIO pin ---- switch ---- GND
#
# Internal pull-up means:
# HIGH = limit NOT reached
# LOW  = limit REACHED

GPIO.setup(UP_LIMIT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(DOWN_LIMIT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)


# ============================================
# Camera Configuration
# ============================================
camera = Picamera2()

# Configure camera for still image capture
camera_config = camera.create_still_configuration(
    main={"size": (1920, 1080)},  # Full HD resolution
    transform = Transform(hflip=1,vflip=1), # For upside down photo
    display="main"
)

camera.configure(camera_config)
camera.set_controls({"ExposureTime":5000})
camera.start()
time.sleep(2)  # Allow camera to warm up

# Create images directory if it doesn't exist
IMAGE_DIR = "captured_images"
os.makedirs(IMAGE_DIR, exist_ok=True)


# ============================================
# Actuator Control Functions
# ============================================
def move(direction, duty=100, duration=None):
    """
    Move actuator in specified direction
    
    Args:
        direction: 'up' or 'down'
        duty: PWM duty cycle (0-100)
        duration: seconds to run (None = run until stopped)
    """
    if direction == 'up':
        GPIO.output(DIR_PIN, GPIO.HIGH)
        print(f"Moving UP at {duty}% duty cycle...")
    else:
        GPIO.output(DIR_PIN, GPIO.LOW)
        print(f"Moving DOWN at {duty}% duty cycle...")
    
    pwm.ChangeDutyCycle(max(0, min(100, duty)))
    
    if duration:
        time.sleep(duration)
        stop()


def stop():
    """Stop actuator movement"""
    pwm.ChangeDutyCycle(0)
    print("Actuator stopped.")


# ============================================
# NEW: Limit Switch Functions
# ============================================

def up_limit_reached():
    """
    Check whether the UP limit switch is activated.

    Returns:
        True if UP limit has been reached.
    """
    return GPIO.input(UP_LIMIT_PIN) == GPIO.LOW


def down_limit_reached():
    """
    Check whether the DOWN limit switch is activated.

    Returns:
        True if DOWN limit has been reached.
    """
    return GPIO.input(DOWN_LIMIT_PIN) == GPIO.LOW


# ============================================
# NEW: Maximum UP Movement
# ============================================

def move_to_max_up(duty=100):
    """
    Move actuator UP until the physical UP limit switch
    is activated.

    No timer is used.

    When the limit is reached:
        - actuator automatically stops
        - maximum reached message is displayed
        - menu is displayed again
    """

    print("\n" + "="*60)
    print("MOVING TO MAXIMUM UP POSITION")
    print("="*60)

    # Check if already at maximum UP position
    if up_limit_reached():
        stop()
        print("\n*** MAXIMUM UP REACHED ***")
        print_menu()
        return

    GPIO.output(DIR_PIN, GPIO.HIGH)

    duty = max(0, min(100, duty))
    pwm.ChangeDutyCycle(duty)

    print(f"Moving UP at {duty}% duty cycle...")
    print("Waiting for UP limit switch...")

    try:
        while True:

            # Check physical limit switch
            if up_limit_reached():

                # Immediately stop actuator
                pwm.ChangeDutyCycle(0)

                print("\n")
                print("*" * 60)
                print("*** MAXIMUM UP REACHED ***")
                print("*" * 60)

                break

            # Small delay prevents unnecessary CPU usage
            time.sleep(0.01)

    except KeyboardInterrupt:
        pwm.ChangeDutyCycle(0)
        print("\nMovement interrupted by user.")

    # Display previous menu again
    print_menu()


# ============================================
# NEW: Maximum DOWN Movement
# ============================================

def move_to_max_down(duty=100):
    """
    Move actuator DOWN until the physical DOWN limit switch
    is activated.

    No timer is used.

    When the limit is reached:
        - actuator automatically stops
        - maximum reached message is displayed
        - menu is displayed again
    """

    print("\n" + "="*60)
    print("MOVING TO MAXIMUM DOWN POSITION")
    print("="*60)

    # Check if already at maximum DOWN position
    if down_limit_reached():
        stop()
        print("\n*** MAXIMUM DOWN REACHED ***")
        print_menu()
        return

    GPIO.output(DIR_PIN, GPIO.LOW)

    duty = max(0, min(100, duty))
    pwm.ChangeDutyCycle(duty)

    print(f"Moving DOWN at {duty}% duty cycle...")
    print("Waiting for DOWN limit switch...")

    try:
        while True:

            # Check physical limit switch
            if down_limit_reached():

                # Immediately stop actuator
                pwm.ChangeDutyCycle(0)

                print("\n")
                print("*" * 60)
                print("*** MAXIMUM DOWN REACHED ***")
                print("*" * 60)

                break

            # Small delay prevents unnecessary CPU usage
            time.sleep(0.01)

    except KeyboardInterrupt:
        pwm.ChangeDutyCycle(0)
        print("\nMovement interrupted by user.")

    # Display previous menu again
    print_menu()


# ============================================
# NEW: Maximum UP + Image Capture
# ============================================

def capture_to_max_up(duty=100, interval=1):
    """
    Move actuator UP until the physical UP limit switch
    is activated while capturing images at regular intervals.

    No movement timer is used.

    Args:
        duty: PWM duty cycle (0-100)
        interval: seconds between image captures
    """

    print("\n" + "="*60)
    print("MAXIMUM UP + IMAGE CAPTURE")
    print("="*60)
    print(f"Duty cycle: {duty}%")
    print(f"Capture interval: {interval} seconds")
    print("Movement will continue until UP limit switch is reached.")
    print("="*60)

    # Check if already at maximum
    if up_limit_reached():
        stop()
        print("\n*** MAXIMUM UP REACHED ***")
        print_menu()
        return

    GPIO.output(DIR_PIN, GPIO.HIGH)

    duty = max(0, min(100, duty))
    pwm.ChangeDutyCycle(duty)

    image_count = 0
    last_capture_time = 0

    # Capture first image immediately
    capture_image(f"max_up_pos{image_count}")
    image_count += 1
    last_capture_time = time.time()

    try:
        while True:

            # Check UP limit switch continuously
            if up_limit_reached():

                # Immediately stop actuator
                pwm.ChangeDutyCycle(0)

                print("\n")
                print("*" * 60)
                print("*** MAXIMUM UP REACHED ***")
                print(f"Total images captured: {image_count}")
                print("*" * 60)

                break

            # Check whether it is time for another image
            current_time = time.time()

            if current_time - last_capture_time >= interval:

                capture_image(f"max_up_pos{image_count}")

                image_count += 1
                last_capture_time = current_time

            time.sleep(0.01)

    except KeyboardInterrupt:

        pwm.ChangeDutyCycle(0)

        print("\nMovement interrupted by user.")
        print(f"Images captured: {image_count}")

    # Display menu again
    print_menu()


# ============================================
# NEW: Maximum DOWN + Image Capture
# ============================================

def capture_to_max_down(duty=100, interval=1):
    """
    Move actuator DOWN until the physical DOWN limit switch
    is activated while capturing images at regular intervals.

    No movement timer is used.

    Args:
        duty: PWM duty cycle (0-100)
        interval: seconds between image captures
    """

    print("\n" + "="*60)
    print("MAXIMUM DOWN + IMAGE CAPTURE")
    print("="*60)
    print(f"Duty cycle: {duty}%")
    print(f"Capture interval: {interval} seconds")
    print("Movement will continue until DOWN limit switch is reached.")
    print("="*60)

    # Check if already at maximum
    if down_limit_reached():
        stop()
        print("\n*** MAXIMUM DOWN REACHED ***")
        print_menu()
        return

    GPIO.output(DIR_PIN, GPIO.LOW)

    duty = max(0, min(100, duty))
    pwm.ChangeDutyCycle(duty)

    image_count = 0
    last_capture_time = 0

    # Capture first image immediately
    capture_image(f"max_down_pos{image_count}")
    image_count += 1
    last_capture_time = time.time()

    try:
        while True:

            # Check DOWN limit switch continuously
            if down_limit_reached():

                # Immediately stop actuator
                pwm.ChangeDutyCycle(0)

                print("\n")
                print("*" * 60)
                print("*** MAXIMUM DOWN REACHED ***")
                print(f"Total images captured: {image_count}")
                print("*" * 60)

                break

            # Check whether it is time for another image
            current_time = time.time()

            if current_time - last_capture_time >= interval:

                capture_image(f"max_down_pos{image_count}")

                image_count += 1
                last_capture_time = current_time

            time.sleep(0.01)

    except KeyboardInterrupt:

        pwm.ChangeDutyCycle(0)

        print("\nMovement interrupted by user.")
        print(f"Images captured: {image_count}")

    # Display menu again
    print_menu()


# ============================================
# Camera Control Functions
# ============================================
def capture_image(prefix="img"):
    """
    Capture a single image with timestamp
    
    Args:
        prefix: filename prefix
    
    Returns:
        filename of captured image
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"{IMAGE_DIR}/{prefix}_{timestamp}.jpg"
    
    camera.capture_file(filename)
    print(f"✓ Image captured: {filename}")
    return filename


def capture_with_movement(direction, duty=100, duration=5, interval=1):
    """
    Move actuator and capture images at regular intervals
    
    Args:
        direction: 'up' or 'down'
        duty: PWM duty cycle (0-100)
        duration: total movement duration in seconds
        interval: time between captures in seconds
    """
    print(f"\n{'='*50}")
    print(f"Starting synchronized capture sequence")
    print(f"Direction: {direction.upper()} | Duration: {duration}s | Interval: {interval}s")
    print(f"{'='*50}\n")
    
    # Start movement
    if direction == 'up':
        GPIO.output(DIR_PIN, GPIO.HIGH)
    else:
        GPIO.output(DIR_PIN, GPIO.LOW)
    
    pwm.ChangeDutyCycle(max(0, min(100, duty)))
    
    start_time = time.time()
    image_count = 0
    
    # Capture images at intervals
    while (time.time() - start_time) < duration:
        capture_image(f"{direction}_pos{image_count}")
        image_count += 1
        
        elapsed = time.time() - start_time
        remaining = duration - elapsed
        
        if remaining > interval:
            time.sleep(interval)
        elif remaining > 0:
            time.sleep(remaining)
        else:
            break
    
    # Stop movement
    stop()
    print(f"\n✓ Sequence complete! Captured {image_count} images.\n")


# ============================================
# Main Interactive Loop
# ============================================
def print_menu():
    """Display command menu"""
    print("\n" + "="*60)
    print("MD10C ACTUATOR + CAMERA CONTROL".center(60))
    print("="*60)
    print("\nCommands:")
    print("  u  - Move UP (manual duration)")
    print("  d  - Move DOWN (manual duration)")
    print("  s  - STOP movement")
    print("  c  - CAPTURE single image")
    print("  a  - AUTO capture with movement (timed sequence)")

    # ============================================
    # NEW OPTIONS
    # ============================================
    print("  U  - Move to MAXIMUM UP position")
    print("  D  - Move to MAXIMUM DOWN position")
    print("  I  - MAXIMUM UP + capture images")
    print("  K  - MAXIMUM DOWN + capture images")

    print("  q  - QUIT program")
    print("="*60)


def get_float_input(prompt, default=None):
    """Get validated float input from user"""
    while True:
        try:
            value = input(prompt).strip()
            if value == "" and default is not None:
                return default
            return float(value)
        except ValueError:
            print("Invalid input. Please enter a number.")


try:
    print_menu()
    
    while True:
        cmd = input("\nEnter command: ").strip()

        # ============================================
        # NEW: MAXIMUM UP
        # ============================================
        if cmd == 'U':

            duty = get_float_input(
                "Duty cycle % (default=100): ",
                default=100.0
            )

            move_to_max_up(duty=duty)

        # ============================================
        # NEW: MAXIMUM DOWN
        # ============================================
        elif cmd == 'D':

            duty = get_float_input(
                "Duty cycle % (default=100): ",
                default=100.0
            )

            move_to_max_down(duty=duty)

        # ============================================
        # NEW: MAXIMUM UP + IMAGE CAPTURE
        # ============================================
        elif cmd == 'I':

            print("\nMaximum UP + Image Capture Setup:")

            interval = get_float_input(
                "Capture interval in seconds (default=1): ",
                default=1.0
            )

            duty = get_float_input(
                "Duty cycle % (default=100): ",
                default=100.0
            )

            # Prevent invalid interval
            if interval <= 0:
                print("Invalid interval. Using 1 second.")
                interval = 1.0

            capture_to_max_up(
                duty=duty,
                interval=interval
            )

        # ============================================
        # NEW: MAXIMUM DOWN + IMAGE CAPTURE
        # ============================================
        elif cmd == 'K':

            print("\nMaximum DOWN + Image Capture Setup:")

            interval = get_float_input(
                "Capture interval in seconds (default=1): ",
                default=1.0
            )

            duty = get_float_input(
                "Duty cycle % (default=100): ",
                default=100.0
            )

            # Prevent invalid interval
            if interval <= 0:
                print("Invalid interval. Using 1 second.")
                interval = 1.0

            capture_to_max_down(
                duty=duty,
                interval=interval
            )
        
        # Manual movement (up/down)
        elif cmd.lower() in ['u', 'd']:

            duration = get_float_input(
                "Enter duration in seconds: "
            )

            capture_now = input(
                "Capture image after movement? (y/n): "
            ).strip().lower()
            
            direction = 'up' if cmd.lower() == 'u' else 'down'

            move(
                direction,
                duty=100,
                duration=duration
            )
            
            if capture_now == 'y':
                capture_image(f"{direction}_manual")
        
        # Stop movement
        elif cmd.lower() == 's':

            stop()
        
        # Single capture
        elif cmd.lower() == 'c':

            capture_image()
        
        # Automated capture with movement
        elif cmd.lower() == 'a':

            print("\nAutomated Capture Sequence Setup:")

            direction = input(
                "Direction (u/d): "
            ).strip().lower()

            if direction not in ['u', 'd']:
                print("Invalid direction. Use 'u' or 'd'.")
                continue
            
            direction = 'up' if direction == 'u' else 'down'

            duration = get_float_input(
                "Total movement duration (seconds): "
            )

            interval = get_float_input(
                "Capture interval (seconds, default=1): ",
                default=1.0
            )

            duty = get_float_input(
                "Duty cycle % (default=100): ",
                default=100.0
            )
            
            capture_with_movement(
                direction,
                duty=duty,
                duration=duration,
                interval=interval
            )
        
        # Quit
        elif cmd.lower() == 'q':

            print("\nShutting down...")
            break
        
        # Unknown command
        else:

            print(
                "Unknown command. Type 'h' for help or use: "
                "u, d, s, c, a, U, D, I, K, q"
            )

except KeyboardInterrupt:

    print("\n\nInterrupted by user (Ctrl+C)")

finally:

    # Cleanup
    print("\nCleaning up...")

    pwm.stop()
    GPIO.cleanup()

    camera.stop()
    camera.close()

    print("✓ GPIO cleaned")
    print("✓ Camera closed")
    print("✓ Program terminated successfully")
