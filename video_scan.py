#!/usr/bin/env python3
"""
Video Scan: Records continuous video while the actuator moves, instead
of capturing individual timed still images. Extract frames afterward
with extract_frames.py - no need to re-run the physical scan if you
want a different frame spacing later.

Usage:
    python3 video_scan.py
"""

import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from libcamera import Transform

# ============================================
# GPIO Configuration
# ============================================
DIR_PIN = 17
PWM_PIN = 18

GPIO.setmode(GPIO.BCM)
GPIO.setup(DIR_PIN, GPIO.OUT)
GPIO.setup(PWM_PIN, GPIO.OUT)

pwm = GPIO.PWM(PWM_PIN, 1000)
pwm.start(0)

# ============================================
# Video Configuration
# ============================================
FRAMERATE = 30  # frames per second - higher = denser data, watch for blur

camera = Picamera2()
video_config = camera.create_video_configuration(
    main={"size": (1920, 1080)},
    transform=Transform(hflip=1, vflip=1),
    controls={"FrameRate": FRAMERATE}
)
camera.configure(video_config)


def scan_with_video(direction, duty, duration, output_filename):
    """
    Records video while moving the actuator.

    Args:
        direction: 'up' or 'down'
        duty: PWM duty cycle (0-100) - use a LOWER value (e.g. 30-50)
              to reduce motion blur compared to full-speed still captures
        duration: seconds to record/move
        output_filename: e.g. 'scan_up_0deg.h264'
    """
    print(f"\nRecording video: {output_filename}")
    print(f"Direction: {direction.upper()} | Duty: {duty}% | Duration: {duration}s")

    encoder = H264Encoder()
    camera.start_recording(encoder, output_filename)

    if direction == 'up':
        GPIO.output(DIR_PIN, GPIO.HIGH)
    else:
        GPIO.output(DIR_PIN, GPIO.LOW)

    pwm.ChangeDutyCycle(max(0, min(100, duty)))

    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        print("\nInterrupted.")

    pwm.ChangeDutyCycle(0)
    camera.stop_recording()

    print(f"Done. Saved to {output_filename}")
    print(f"Recorded at {FRAMERATE} fps - use this with extract_frames.py")


def get_float_input(prompt, default=None):
    while True:
        try:
            value = input(prompt).strip()
            if value == "" and default is not None:
                return default
            return float(value)
        except ValueError:
            print("Invalid input.")


if __name__ == "__main__":
    try:
        camera.start()
        time.sleep(2)

        direction = input("Direction (u/d): ").strip().lower()
        direction = 'up' if direction == 'u' else 'down'

        duty = get_float_input("Duty cycle % (recommend 30-50 to reduce blur, default=40): ", default=40.0)
        duration = get_float_input("Duration in seconds (e.g. 44 for full travel): ")

        angle_label = input("Angle label for filename (e.g. 0, 120, 240): ").strip()
        output_filename = f"scan_{direction}_{angle_label}deg.h264"

        scan_with_video(direction, duty, duration, output_filename)

    finally:
        pwm.stop()
        GPIO.cleanup()
        camera.stop()
        camera.close()
        print("Cleaned up.")