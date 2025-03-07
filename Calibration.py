
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


# Configuration for capturing HQ images
camera_config = picam.create_video_configuration(
    main={'format': 'RGB888', "size": config.image_size},
    buffer_count=config.image_buffer)
picam.configure(camera_config)
picam.start()

# Capture image for calculating the center
testimg = picam.capture_array()
shape = testimg.shape

# Center Point of the Image in (X,Y) Coordinates
image_center = (int(shape[1]//2), int(shape[0]//2))
(reference_x, reference_y) = image_center

trigger_time=5
calibDeviations=perform_calibration(trigger_time)
print(calibDeviations)


# Compute travelled distance s
s = [[(a**2 + b**2)**0.5 for a, b in calibDeviations]]

# Compute pixels per second
pixels_per_second = [x/trigger_time for x in s]
print(pixels_per_second)

# Compute rotation angle alpha
alpha = np.arctan(b/a for a, b in calibDeviations)


# Average results
s_averaged = np.mean(s)  

pixels_per_second_averaged = np.mean(pixels_per_second)

# Compute pulse_multiplier as inverse of averaged pixels per second
pulse_multi = 1/pixels_per_second_averaged

alpha_averaged = np.mean(alpha)