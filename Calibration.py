
"""
This Python script offers a calibration routine for the Moon Guider to account for different mounts 
and different mounting angles. It calculates the pixels that the camera moves per second when a relay
is triggered and the angle that the camera's coordinate system is rotated by compared to the mount's
coordinate system and writes the values into the config.ini file for further processing.
"""


import os
import time
import cv2 as cv
from picamera2 import Picamera2
import calc
import relay_handling
import config_loader





def capture():
    # Initialize Picamera2
    picam = Picamera2()

    # Specify the folder path
    folder_path = "calibration_pics"

    # Check if the folder exists, and if not, create it
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Picam Configuration
    camera_config = picam.create_video_configuration(
        main={'format': 'RGB888', "size": (4056, 3040)},
        buffer_count=7,
    )
    picam.configure(camera_config)

    # Start the camera
    picam.start()

    # Display the live feed
    while True:
        img = picam.capture_array()
        cv.namedWindow('Camera Output', cv.WINDOW_NORMAL)
        cv.setWindowProperty('Camera Output', cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)
        cv.imshow('Camera Output', img)
        key = cv.waitKey(1)
        if key != -1:  # Exit loop on key press
            break

    # Close the display window
    cv.destroyAllWindows()

    # Capture and save a single image
    img = picam.capture_array()
    print("Image captured.")

    image_path = os.path.join(folder_path, 'calibration_img.png')
    cv.imwrite(image_path, img)

    print(f"Image saved at: {image_path}")

    # Cleanup
    cv.destroyAllWindows()



# Read the moon's initial starting position


# For each moving direction (Ra+, Ra-, Dec+, Dec-): Trigger the relay for n seconds, read end position and move back


    # Read starting position again and compare as a fail-safe

    # Compute travelled distance s

    # Compute pixels per second

    # Compute rotation angle alpha


# Average results


# Compute pulse_multiplier and write it into the config.ini file


