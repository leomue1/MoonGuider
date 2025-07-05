# -*- coding: utf-8 -*-
"""
Initializes and handles the actuation of the relay board during normal operation as well
as cloud obstruction, calculates the required signals.

Threading is used for actuating the relays during image processing time.

classes: guide

"""

import RPi.GPIO as GPIO
import time
import threading
import numpy as np


class guide:
    def __init__(self, log, config):
        """
        Initializes attributes from the configuration parameters and creates locks and threads
        for the relay activation. If a rotation is set in the configuration, the order of the
        relay pins will be switched accordingly. Initializes the Raspberry Pi GPIO and then
        pulses every relay once.

        Parameters
        ----------
        log : log instance from calc.py
        config : configuration instance from config_loader.py

        Returns
        -------
        None.

        """

        self.active_deviation = (None, None)
        self.active = [False, False, False, False]
        self.mode_info = None
        self.deviation_records = [(0, 0)]
        self.sbx = []
        self.sby = []

        # Add logging
        self.log = log
        self.log.add('Activity', ["Time", "Duration", "Direction"])

        # Get settings and parameters from config
        self.pulse_multiplier = config.pulse_multiplier
        self.margin = config.margin
        self.button_pin = config.button_pin
        self.record_buffer = config.record_buffer
        self.rotation_angle = config.rotation_angle
        self.cloud_mode = config.cloud_mode

        # Pin order is RIGHT, LEFT, DOWN, UP ; -RA, +RA, -DEC, +DEC
        self.relay_pins = config.relay_pins
        
        # Create a locks for thread synchronization
        self.gpio_lock = threading.Lock()
        self.log_lock = threading.Lock()
        self.active_lock = threading.Lock()
        self.active_deviation_lock = threading.Lock()

        # Create threads for relay activation
        self.activate_thread_ra = threading.Thread(target=self.activate_ra, daemon=True)
        self.activate_thread_dec = threading.Thread(target=self.activate_dec, daemon=True)
              
        # Errorcheck cloudmode
        if self.cloud_mode not in (None, "repeat", "Repeat"):
            raise ValueError("Cloud mode not correctly specified.")

        # Initialize Raspberry Pi GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        for pin in self.relay_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)

        # Pulse every relay once
        for pin in self.relay_pins:
            self.pulse(pin, 1)
    
    def rotate_deviation(self, x, y):
        """
        Rotates the deviation measured in the x-y camera coordinate system into the RA-DEC mount
        coordinate system
        """

        theta = np.radians(self.rotation_angle)
        R = np.array([
            [np.cos(theta), np.sin(theta)],
            [-np.sin(theta), np.cos(theta)]
        ])
        rotated = R @ np.array([x, y])
        return tuple(rotated)
    

    def to(self, deviation=(None, None)):

        # Check if no target is found, deviation is none, therefore cloud mode will take over
        # Using self.active_deviation as basis for relay activation
        # Returns: None

        if None in deviation:
            self.active_deviation = self.cloud_handling()
        else:
            # Check if contact has been regained after being in repeat mode
            if self.mode_info == "Repeat":
                self.deviation_records = []

            self.mode_info = "Active"
            self.active_deviation = self.rotate_deviation(*deviation)
            self.record(deviation)

        # Start threads for relay activation for each axis if not already active
        if not self.activate_thread_ra.is_alive():
            self.activate_thread_ra = threading.Thread(target=self.activate_ra, daemon=True)
            self.activate_thread_ra.start()
        if not self.activate_thread_dec.is_alive():
            self.activate_thread_dec = threading.Thread(target=self.activate_dec, daemon=True)
            self.activate_thread_dec.start()

        return

    def cloud_handling(self):
        # If cloud mode is set to None, set deviation to 0 to turn off relays
        # Returns deviation

        if self.cloud_mode is None:
            self.mode_info = "Inactive"
            return (0, 0)
        # Repeat previous signals by cycling through recording
        else:
            self.mode_info = "Repeat"
            temp = self.deviation_records[0]
            self.deviation_records.pop(0)
            self.deviation_records.append(temp)
            return temp

        return

    def record(self, deviation):
        # Appends deviations to list of recordings

        self.deviation_records.append(deviation)
        if len(self.deviation_records) > self.record_buffer:
            self.deviation_records.pop(0)
        return

    def activate_ra(self):  # left right
        """
        Main functions for interpreting the deviation as a correction signal for the
        respective axes. Checks for deviation within margin and calculates signal
        length based on the deviation and pulse_multiplier. The functions for switching
        the pins on and off will be called. Activity is communicated through the active
        attribute and logged with a time-stamp. Will always be executed as threads.
        """

        # Set parameters as to not check in shared memory
        ad = self.active_deviation
        margin = self.margin
        xdev = ad[0]
        # Check if deviation is over margin
        if abs(xdev) <= margin:
            pass
        else:
            (right, left) = (xdev > margin, xdev < margin * -1)

            # calculate pulse time
            temp = (abs(xdev)) * self.pulse_multiplier
            duration = temp if temp < 3 else 3

            # Report activated pins to list
            with self.active_lock:
                self.active[0] = right
                self.active[1] = left

            direction = 'right' if right else 'left'

            # Log activity
            with self.log_lock:
                self.log.add('Activity', [time.time(), duration, direction])

            # Do the pulsing and set pins to off in info list
            self.switch_pin_on([right, left, False, False])
            time.sleep(duration)
            self.switch_pin_off([right, left, False, False])
            with self.active_lock:
                self.active[0] = 0
                self.active[1] = 0

    def activate_dec(self):  # up down
        """
        Same as activate_ra but other axis
        """
        # Set parameters as to not check in shared memory
        ad = self.active_deviation
        margin = self.margin
        ydev = ad[1]
        # Check if deviation is over margin
        if abs(ydev) <= margin:
            pass
        else:
            (down, up) = (ydev > margin, ydev < margin * -1)

            # calculate pulse time
            temp = (abs(ydev)) * self.pulse_multiplier
            duration = temp if temp < 3 else 3

            # Report activated pins to list
            with self.active_lock:
                self.active[2] = down
                self.active[3] = up

            direction = 'down' if down else 'up'

            # Log activity
            with self.log_lock:
                self.log.add('Activity', [time.time(), duration, direction])

            # Do the pulsing and set pins to off in info list
            self.switch_pin_on([False, False, down, up])
            time.sleep(duration)
            self.switch_pin_off([False, False, down, up])
            with self.active_lock:
                self.active[2] = 0
                self.active[3] = 0

    def switch_pin_on(self, directions=['Right', 'Left', 'Down', 'Up']):  # -RA, +RA, -DEC, +DEC
        # Activate pins based on the order of booleans in the list
        with self.gpio_lock:
            for pin, direction in zip(self.relay_pins, directions):
                if direction:
                    GPIO.output(pin, GPIO.LOW)
        return

    def switch_pin_off(self, directions=['Right', 'Left', 'Down', 'Up']):  # -RA, +RA, -DEC, +DEC
        # Deactivate pins based on the order of booleans in the list
        with self.gpio_lock:
            for pin, direction in zip(self.relay_pins, directions):
                if direction:
                    GPIO.output(pin, GPIO.HIGH)
        return

    def button_is_pressed(self):
        # Check for button press and return True
        return GPIO.input(self.button_pin) == GPIO.LOW

    def pulse(self, pin, count=1, uptime=0.1, downtime=0.1):
        # Pulse specified pin number
        for i in range(count):
            GPIO.output(pin, GPIO.LOW)
            time.sleep(uptime)
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(downtime)

        return

    def showactive(self):
        # Return list of strings of active pins and mode info
        act = []

        if self.active[0]:
            act.append("-RA")
        if self.active[1]:
            act.append("+RA")
        if self.active[2]:
            act.append("-DEC")
        if self.active[3]:
            act.append("+DEC")

        act.append(self.mode_info)

        return(act)

    def stop(self):
        # Terminate the guider safely
        print("Waiting for threads to finish...")
        self.activate_thread_ra.join()
        self.activate_thread_dec.join()

        self.switch_pin_off([True, True, True, True])

        GPIO.cleanup()
        return
