
"""
This Python script offers a calibration routine for the Moon Guider to account for different mounts 
and different mounting angles. It calculates the pixels that the camera moves per second when a relay
is triggered and the angle that the camera's coordinate system is rotated by compared to the mount's
coordinate system and writes the values into the config.ini file for further processing.
"""
import csv
import os
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

def average_moon_position(samples, delay):
    """
    This function takes a number of samples of the current position with a certain time delay 
    between each sample and outputs the average of the x and y positions and the radius. The
    amount of samples and the delay can be specified on the Moon Guider screen before running 
    the program.
    """
    x_vals, y_vals, r_vals = [], [], []
    for _ in range(samples):
        img = picam.capture_array()
        processed = clc.preprocessing(img)
        x, y, r = clc.moonposition(processed)
        x_vals.append(x)
        y_vals.append(y)
        r_vals.append(r)
        time.sleep(delay)
    return (
        sum(x_vals) / len(x_vals),
        sum(y_vals) / len(y_vals),
        sum(r_vals) / len(r_vals),
    )

def perform_calibration(moving_time, samples, delay):
    """ 
    Outputs the image of the camera to the display, marking a detected target. The
    user then needs to confirm that the correct target is found by pressing the button.
    The function now iterates over the relay pins. Each relay is activated for a set time. 
    Before and after each movement, the moon position is detected and the deviations are stored.
    After each movement, the camera returns to the initial position by activating the opposite
    direction's relay.

    """

    deviations = []
    initial_positions = []
    final_positions = []

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
            print("Calibration in Progress")
            time.sleep(1)
            break

    # Get target position again
    org_image = picam.capture_array()
    processed = clc.preprocessing(org_image)
    (target_x, target_y, _) = clc.moonposition(processed)

    # Map each direction to its opposite
    direction_map = {
    "right": "left",
    "left": "right",
    "up": "down",
    "down": "up"
    }

    # Create a direction → pin mapping from guide.relay_pins
    directions = ["right", "left", "down", "up"]
    pin_map = dict(zip(directions, guide.relay_pins))

    # Calibration loop
    for direction in directions:
        pin = pin_map[direction]
        opposite_pin = pin_map[direction_map[direction]]

        # Capture initial position loop 
        org_image = picam.capture_array()
        processed = clc.preprocessing(org_image)
        x_0, y_0, r_0 = average_moon_position(samples, delay)
        initial_positions.append((x_0, y_0, r_0))
            

        print(f"\nTesting direction '{direction}' (pin {pin})...")
        guide.pulse(pin, 1, moving_time, 0.2)
        time.sleep(1)  # Allow camera to stabilize

        # Capture position after moving
        org_image = picam.capture_array()
        processed = clc.preprocessing(org_image)
        x, y, r = average_moon_position(samples, delay)
        final_positions.append((x, y, r))

        # Calculate deviation
        deviation = clc.get_deviation((x, y), (x_0, y_0))
        deviations.append(deviation)
        print(f"Detected deviation after moving {direction}: {deviation}")

        # Move back to the starting position
        print(f"Returning to original position using '{direction_map[direction]}' (pin {opposite_pin})...")
        guide.pulse(opposite_pin, 1, moving_time, 0.2)
        time.sleep(1)  # Let system settle before next direction

    # Wait for button press to finish
    print("\nPress Button to continue")
    while True:
        if guide.button_is_pressed():
            break

        return deviations, initial_positions, final_positions

  


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

trigger_time = input("Enter trigger time in seconds:")
# Convert it to a float (with error handling)
try:
    trigger_time = float(trigger_time)
except ValueError:
    print("Invalid input. Please enter a number.")
    exit(1)

avg_samples = input("How many samples should be taken for averaging?:")
try:
    avg_samples = int(avg_samples)
except ValueError:
    print("Invalid input. Please enter integer for samples and float for delay.")
    exit(1)

avg_delay = input("How much delay between the averaging samples?:")
try:
    avg_delay = float(avg_delay)
except ValueError:
    print("Invalid input. Please enter integer for samples and float for delay.")
    exit(1)

cycles = input("Enter number of Calibration cycles:")
try:
    cycles = int(cycles)
except ValueError:
    print("Invalid input. Please enter an integer.")
    exit(1)

for i in range(cycles):
    print(f"\nStarting calibration run {i + 1}...")
    calibDeviations, calibInitialPos, calibFinalPos = perform_calibration(trigger_time, avg_samples, avg_delay)

    csv_filename = f"calibration_results_{int(trigger_time)}s_mov.csv"
    file_exists = os.path.isfile(csv_filename)

    with open(csv_filename, mode="a", newline='') as f:
        writer = csv.writer(f)

        # Write header once if needed
        if not file_exists:
            writer.writerow([
                "RunID", "Direction",
                "Initial_X", "Initial_Y", "Initial_Radius",
                "Final_X", "Final_Y", "Final_Radius",
                "Dev_X", "Dev_Y"
            ])

        run_id = int(time.time())
        directions = ["right", "left", "down", "up"]

        for j, (init, final, dev) in enumerate(zip(calibInitialPos, calibFinalPos, calibDeviations)):
            direction = directions[j]
            writer.writerow([
                run_id, direction,
                init[0], init[1], init[2],     # Initial position + radius
                final[0], final[1], final[2],  # Final position + radius
                dev[0], dev[1]                 # X/Y deviation
            ])

    print(f"Calibration run {i + 1} saved to {csv_filename}.")

"""

# Compute travelled distance s
s = [(a**2 + b**2)**0.5 for a, b in calibDeviations]
print(s)

# Compute pixels per second
pixels_per_second = [a/trigger_time for a in s]
print(pixels_per_second)

# Compute rotation angle alpha
alpha = [np.degrees(np.arctan(b / a)) if a != 0 else np.pi/2 for a, b in calibDeviations]
alpha_converted = [float(x)for x in alpha]
print(alpha_converted)

# Average results
s_averaged = np.mean(s)  
print(s_averaged)

pixels_per_second_averaged = np.mean(pixels_per_second)
print(pixels_per_second_averaged)

# Compute pulse_multiplier as inverse of averaged pixels per second
pulse_multi = 1/pixels_per_second_averaged
print(pulse_multi)


# Load and read config.ini file
edit_config = configparser.ConfigParser()
edit_config.read("config.ini")

# Modify pulse_multiplier in all file sections
# Specify value that should be updated
updated_value = "pulse_multiplier"
# Loop through all sections to check if pulse multiplier is in there. If yes, replace it with the 
# new value
for section in edit_config.sections:
    if updated_value in edit_config[section]:
        edit_config[section][updated_value] = pulse_multi
# Save changes back to the file
with open("config.ini", "w") as configfile:
    edit_config.write(configfile)

print("Updated {updated_value} to {pulse_multi} in every relevant section successfully.")

alpha_averaged = np.mean(alpha_converted)
print(alpha_averaged)

"""