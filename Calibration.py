
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


def average_moon_position(samples, delay, picam, clc):

    """
    This function takes a number of samples of the current position with a certain time delay 
    between each sample and outputs the average of the x and y positions and the radius in order
    to minimize errors. The amount of samples and the delay can be specified in config.ini before 
    running the program.
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
        round(sum(x_vals) / len(x_vals), 2),
        round(sum(y_vals) / len(y_vals), 2),
        round(sum(r_vals) / len(r_vals), 2),
    )

def normalize(vectors):
    #This function takes in a deviation vector and returns the normalized vector"

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / norms

def backlash_check(deviations, moving_time, threshold_percentage):

    """
    This function selects the first and second deviation vector of each directional movement
    that has been triggered. Then both magnitudes are computed and compared and if the difference 
    exceeds the percentage threshold, the backlash results are logged for this direction and a 
    message is output to the console.
    """

    direction_labels = ["right", "left", "down", "up", "left", "right", "up", "down"]
    backlash_estimates = {}
    backlash_info = {}
    backlash_messages = []

    # Get first and second pulse of a direction.
    for i in range(0, len(deviations), 2):
        dev1 = deviations[i]
        dev2 = deviations[i + 1]
        direction = direction_labels[i // 2]

        # Compute magnitudes
        mag1 = (dev1[0]**2 + dev1[1]**2)**0.5
        mag2 = (dev2[0]**2 + dev2[1]**2)**0.5

        if mag2 == 0:
            backlash_messages.append(f" {direction.upper()}: Pulse 2 has zero movement, can't compare.")
            continue
        
        # Compute percentage difference between both pulses
        percent_diff = abs(mag2 - mag1) / mag2
        backlash_messages.append(f"{direction.upper()} | Pulse 1: {mag1:.2f}px, Pulse 2: {mag2:.2f}px → Δ: {percent_diff:.0%}")

        # Compare to threshold value and log values in case threshold is exceeded.
        if percent_diff > threshold_percentage:
            loss_pct = 1 - (mag1 / mag2)
            backlash_time = loss_pct * moving_time

            backlash_estimates[direction] = backlash_time
            backlash_info[i] = (loss_pct, backlash_time)
            backlash_info[i + 1] = (loss_pct, backlash_time)

            backlash_messages.append(f"⚠️  BACKLASH DETECTED in {direction.upper()}")
            backlash_messages.append(f"   → Estimated backlash: {loss_pct*100:.1f}% of motion lost")
            backlash_messages.append(f"   → Add ~{backlash_time:.2f} seconds to pre-load movement")

    return backlash_estimates, backlash_info, backlash_messages

def perform_calibration(moving_time, samples, delay, guide, picam, clc):
    """
    This function performs the main calibration movements and outputs deviations for following 
    computations and initial and final positions for logging.
    It has two specific directional passes that are run:
    - Pass 1: right, left, down, up
    - Pass 2: left, right, up, down
    Each direction has 2 pulses, each logged with deviation.
    """

    deviations = []
    initial_positions = []
    final_positions = []

    # Defines movement patterns
    pass1 = ["right", "left", "down", "up"]
    pass2 = ["left", "right", "up", "down"]
    passes = [pass1, pass2]

    # Map direction names to corresponding relay pins
    pin_map = dict(zip(["right", "left", "down", "up"], guide.relay_pins))

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
    
    # Loop over both direction passes
    for cycle, direction_list in enumerate(passes, start=1):
        print(f"\n--- Starting Calibration Cycle {cycle} ---")

        for direction in direction_list:
            pin = pin_map[direction]

            for pulse in range(2):
                print(f"\nCycle {cycle} | Direction: {direction.upper()} | Pulse {pulse + 1}/2")

                # Capture initial positions
                x_0, y_0, r_0 = average_moon_position(samples, delay, picam, clc)
                initial_positions.append((x_0, y_0, r_0))

                # Move for the amount of seconds specified as moving_time in current direction
                guide.pulse(pin, 1, moving_time, 0.2)
                time.sleep(1)

                # Capture final positions
                x, y, r = average_moon_position(samples, delay, picam, clc)
                final_positions.append((x, y, r))

                # Compute deviation between initial and final position
                deviation = clc.get_deviation((x, y), (x_0, y_0))
                deviations.append(deviation)

                print(f"Deviation: {deviation}")

    print("\nPress Button to continue")
    while not guide.button_is_pressed():
        pass

    return deviations, initial_positions, final_positions


def main(config=None, picam=None):
    # Initialize default config and camera if not provided by main.py
    if config is None:
        config = config_loader.configuration()
    if picam is None:
        picam = Picamera2()
        # Configuration for capturing HQ images
        camera_config = picam.create_video_configuration(
            main={'format': 'RGB888', "size": config.image_size},
            buffer_count=config.image_buffer)
        picam.configure(camera_config)
        picam.start()

    # Initialize class instances and load parameters
    log = calc.log(config)
    guide=relay_handling.guide(log, config)
    clc = calc.calculation(config)

    relay_pins = config.relay_pins
    calibration_pulse_length = config.calibration_pulse_length
    avg_samples = config.samples
    avg_delay = config.delay


    # Capture image for calculating the center
    testimg = picam.capture_array()
    shape = testimg.shape

    # Center Point of the Image in (X,Y) Coordinates
    image_center = (int(shape[1]//2), int(shape[0]//2))
    (reference_x, reference_y) = image_center
    
    # Clear any lingering key events before starting calibration
    for _ in range(10):
        cv.waitKey(1)

    print("\nStarting calibration run...")
    # Execute calibration
    calibDeviations, calibInitialPos, calibFinalPos = perform_calibration(
        calibration_pulse_length, avg_samples, avg_delay, guide, picam, clc
    )

    print("\n Checking for potential backlash in all directions...")
    backlash_threshold_percentage = config.backlash_threshold_percentage
    backlash_estimates, backlash_info, messages = backlash_check(
        calibDeviations, calibration_pulse_length, backlash_threshold_percentage
    )

    for line in messages:
        print(line)

    # Only use the second pulse from each direction (i.e., pulse index 1, 3, 5, ..., 15)
    second_pulses = [i for i in range(len(calibDeviations)) if i % 2 == 1]

    # Filter to second-pulse-only values
    selectedDeviations = [calibDeviations[i] for i in second_pulses]

    # Direction sequence for the 8 second-pulse measurements
    pass1 = ["right", "left", "down", "up"]
    pass2 = ["left", "right", "up", "down"]
    directions_sequence = pass1 + pass2

    # Group deviations by direction
    deviation_dict = { "right": [], "left": [], "down": [], "up": [] }

    for direction, deviation in zip(directions_sequence, selectedDeviations):
        deviation_dict[direction].append(deviation)

    # Compute average deviation per direction
    averagedDeviations = []
    for direction in ["right", "left", "down", "up"]:
        d1, d2 = deviation_dict[direction]
        avg_x = (d1[0] + d2[0]) / 2
        avg_y = (d1[1] + d2[1]) / 2
        averagedDeviations.append((avg_x, avg_y))

    # Save results to CSV-file
    csv_filename = f"calibration_results_{int(calibration_pulse_length)}s.csv"
    file_exists = os.path.isfile(csv_filename)

    # Open CSV file in append mode to store calibration results
    with open(csv_filename, mode="a", newline='') as f:
        writer = csv.writer(f)

        # Write header row if the file is new
        if not file_exists:
            writer.writerow([
                "RunID", "Direction", "Cycle", "Pulse",
                "Initial_X", "Initial_Y", "Initial_Radius",
                "Final_X", "Final_Y", "Final_Radius",
                "Dev_X", "Dev_Y",
                "Backlash_Pct", "Backlash_Sec"
            ])

        # Unique ID for this run based on timestamp
        run_id = int(time.time())

        # Full direction sequence from both calibration passes
        directions_sequence = pass1 + pass2

        # Write data for each pulse
        for j, (init, final, dev) in enumerate(zip(calibInitialPos, calibFinalPos, calibDeviations)):
            # Determine direction index and pulse number
            direction_index = j // 2  # two pulses per direction
            pulse_number = (j % 2) + 1  # 1 or 2

            # Get direction name and cycle (1 or 2)
            direction = directions_sequence[direction_index]
            cycle_number = 1 if direction_index < 4 else 2

            # Get backlash info if available; otherwise default to zeros
            loss_data = backlash_info.get(j, (0.0, 0.0))
            loss_pct, loss_time = loss_data

            # Write a single row of calibration data
            writer.writerow([
                run_id, direction, cycle_number, pulse_number,
                init[0], init[1], init[2],
                final[0], final[1], final[2],
                dev[0], dev[1],
                round(loss_pct, 4), round(loss_time, 4)
            ])

    print(f"Final calibration results saved to {csv_filename}.")


    """
    This section does the calculations for the final results of the calibration and writes them 
    into the config.ini file.
    """

    # Compute travelled distance s for every direction
    s = [(a**2 + b**2)**0.5 for a, b in averagedDeviations]

    # Compute pixels per second for every direction
    pixels_per_second = [a / calibration_pulse_length for a in s]

    # Compute average of pixels per second over all directions
    pixels_per_second_averaged = np.mean(pixels_per_second)

    # Compute pulse multiplier
    pulse_multi = 1 / pixels_per_second_averaged

    # Define expected mount unit vectors
    mount_vectors = np.array([
        [0, 1],   # down
        [0, -1],  # up
        [-1, 0],   # right
        [1, 0]   # left
    ])

    # Normalize mount and camera vectors to enable comparison
    mount_norm = normalize(mount_vectors)
    camera_norm = normalize(averagedDeviations)

    # Compute the optimal rotation angle using least-squares fit
    # Solve for R in: camera_norm ≈ R @ mount_norm
    U, _, VT = np.linalg.svd(camera_norm.T @ mount_norm)
    R = U @ VT

    # Extract angle from rotation matrix
    theta_rad = np.arctan2(R[1, 0], R[0, 0])
    theta_deg = np.degrees(theta_rad)


    # Write pulse_multiplier and rotation_angle back to all sections of config.ini (excluding DEFAULT)
    
    # Load the existing configuration file
    edit_config = configparser.ConfigParser()
    edit_config.read("config.ini")

    # Keys to be updated in each section
    updated_value_1 = "pulse_multiplier"
    updated_value_2 = "rotation_angle"
    updated_count = 0     # Track how many sections are updated

    # Loop through all sections (excluding DEFAULT) and update values
    for section in edit_config.sections():
        if section == "DEFAULT":
            continue

        # Update values with desired rounding
        edit_config[section][updated_value_1] = str(round(pulse_multi, 5))  
        edit_config[section][updated_value_2] = str(round(theta_deg, 2))    
        updated_count += 1

    # Write the updated config back to file
    with open("config.ini", "w") as configfile:
        edit_config.write(configfile)

    print(f" Updated {updated_count} sections in config.ini (excluding DEFAULT):")
    print(f"    pulse_multiplier = {round(pulse_multi, 5)}")
    print(f"    rotation_angle   = {round(theta_deg, 2)}")

# Run main function if calibration is called standalone
if __name__ == '__main__':
    main()
