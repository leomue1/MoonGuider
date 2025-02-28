
"""
This Python script offers a calibration routine for the Moon Guider to account for different mounts 
and different mounting angles. It calculates the pixels that the camera moves per second when a relay
is triggered and the angle that the camera's coordinate system is rotated by compared to the mount's
coordinate system and writes the values into the config.ini file for further processing.
"""


# Read the moon's initial starting position


# For each moving direction (Ra+, Ra-, Dec+, Dec-): Trigger the relay for n seconds, read end position and move back


    # Read starting position again and compare as a fail-safe

    # Compute travelled distance s

    # Compute pixels per second

    # Compute rotation angle alpha


# Average results


# Compute pulse_multiplier and write it into the config.ini file


