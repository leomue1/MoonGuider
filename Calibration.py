
"""
This Python script offers a calibration routine for the Moon Guider to account for different mounts 
and different mounting angles. It calculates the pixels that the camera moves per second when a relay
is triggered and the angle that the camera's coordinate system is rotated by compared to the mount's
coordinate system and writes the values into the config.ini file for further processing.
"""

import numpy as np
import time
import cv2 as cv
from picamera2 import Picamera2
import calc
import relay_handling
import config_loader
import configparser

#Initialize outside classes
config=config_loader.configuration()
log = calc.log(config)
guide=relay_handling.guide(log, config)
clc = calc.calculation(config)
picam=Picamera2()

relay_pins = config.relay_pins

def perform_calibration(moving_time):
    """ Outputs the image of the camera to the display, marking a detected target. The
        user then needs to confirm that the correct target is found by pressing the button.
        The function now iterates over the relay pins, activating them in pulses. After each
        pin the target location is checked again and the deviation is printed to the console.
        Can be skipped by pressing any key.

        Returns: None
    """

    deviations = []

    # Capture loop for camera images and target detection and marking
    while True:
        cv.namedWindow('Camera Output', cv.WINDOW_NORMAL)
        cv.setWindowProperty(
            'Camera Output', cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)

        org_image = picam.capture_array()
        processed = clc.preprocessing(org_image)

        (target_x, target_y, _) = clc.moonposition(processed)

        marked = clc.targetmarkers(
            target_x,
            target_y,
            _,
            target_x,
            target_y,
            (0, 0),
            org_image,
            "Press any key to skip relay test.\nPress Button if correct Target is found."
        )

        cv.imshow('Camera Output', marked)
        key = cv.waitKey(1)

        if key != -1:
            return

        # Confirm correct target
        if guide.button_is_pressed():
            cv.destroyAllWindows()
            print("Relay Testing in Progress...\nThis will take 40s")
            time.sleep(1)
            break

    # Get target position again
    org_image = picam.capture_array()
    processed = clc.preprocessing(org_image)
    (target_x, target_y, _) = clc.moonposition(processed)

    # Iterate over each pin, checking for target between activations
    for pin, direction in zip(guide.relay_pins, ["right", "left", "down", "up"]):
        org_image = picam.capture_array()
        processed = clc.preprocessing(org_image)

        # Obtain initial test position
        (x_0, y_0, r_0) = clc.moonposition(processed)

        print(f"Testing pin {pin} ({direction})...")
        guide.pulse(pin, moving_time, 2, 0.2)
        
        org_image = picam.capture_array()
        processed = clc.preprocessing(org_image)
        # Obtain final test position
        (x, y, r) = clc.moonposition(processed)
        deviation = clc.get_deviation((x, y), (x_0, y_0))
        deviations.append(deviation)
        print(f"Detected deviation: {deviation}")
    print("\nPress Button to continue")
    while True:
        if guide.button_is_pressed():
            break

    return deviations





