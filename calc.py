# -*- coding: utf-8 -*-
"""
Created on Tue Nov  7 21:08:05 2023

@author: Tobias Kurz

This Python script offers functions for processing the Images taken by the Pi.
This includes preprocessing, detection of the moon and calculating deviations
from the center. Handles bufferung, overlay and exporting log file

Classes:
- Calculation
- Buffer
- Log

Ensure OpenCV (cv2), NumPy and pandas are installed.

"""


import cv2 as cv
import numpy as np
import time
import pandas as pd


class calculation:
    def __init__(self, config):

        # Initialize attributes from config to calculation values

        self.blur = config.blur
        self.overlay = config.overlay
        self.in_scale = config.in_scale
        self.dp = config.dp
        self.param1 = config.param1
        self.param2 = config.param2
        self.out_scale = config.out_scale

        self.minRadius = 50
        self.maxRadius = 400

    def preprocessing(self, img):

        # Turn image into grey version (1 channel)
        img = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

        # Blur to remove noise
        img = cv.blur(img, (int(self.blur), int(self.blur))) if self.blur else img

        return img

    def targetmarkers(self,
                      target_x,
                      target_y,
                      target_radius,
                      ref_x,
                      ref_y,
                      deviation,
                      img,
                      handover_value):
        """
        Adds all the informational overlays to the camera images and resizes the output if
        specified. This includes: target markings, reference point markings, deviation arrow,
        white information bar overlay. Additionally to the target location and deviation, the
        information bar outputs any text that is specified in the function input as the
        handover_value. The information bar automatically jumps to the top of the image if it
        would obstruct the view of the target.

        Parameters
        ----------
        target_x; target_y, target_radius : Target Position and radius in frame in pixels
        ref_x; ref_y : Reference position in frame in pixels
        deviation :  Deviation from target as tuple
        img : Image for the overlay
        handover_value : String to display in information bar

        Returns
        -------
        Image with overlay

        """

        # Check shape for error mitigation then turn to greyscale
        if len(img.shape) == 2:
            img = cv.cvtColor(img, cv.COLOR_GRAY2BGR)

        img = cv.resize(img, None, fx=self.out_scale, fy=self.out_scale,
                        interpolation=cv.INTER_LINEAR)

        if img.shape[2] == 4:
            # Split the image into its channels
            channels = cv.split(img)

            # Keep only the first three channels (RGB)
            img = cv.merge(channels[:3])

        # Set parameters for adjusting markings
        (height, width) = img.shape[0:2]
        line_color = (0, 0, 255)  # Red in BGR format

        # Define the thickness of the lines
        line_thickness = int(8 * self.out_scale) if int(8 * self.out_scale) >= 1 else 1

        # Draw reference point in lines
        if not None in (ref_x, ref_y):
            scl_ref_x = int(ref_x * self.out_scale)
            scl_ref_y = int(ref_y * self.out_scale)
            cv.line(img, (0, scl_ref_y), (width, scl_ref_y), line_color, line_thickness * 2)
            cv.line(img, (scl_ref_x, 0), (scl_ref_x, height), line_color, line_thickness * 2)

        if None in deviation:  # No target is tracked

            cv.line(img, (0, 0), (width, height), line_color, line_thickness)
            cv.line(img, (0, height), (width, 0), line_color, line_thickness)

            cv.circle(img, (width // 2, height // 2),
                      int(self.minRadius * self.out_scale),
                      line_color, line_thickness)
            cv.circle(img, (width // 2, height // 2),
                      int(self.maxRadius * self.out_scale),
                      line_color, line_thickness)

        elif None in (target_x, target_y):

            # Target is not found but deviation is generated through prediction
            # or last deviation
            scl_devx = int(deviation[0] * self.out_scale)
            scl_devy = int(deviation[1] * self.out_scale)
            try:
                # Draw deviation Arrow
                cv.arrowedLine(img, (scl_ref_x, scl_ref_y),
                               (scl_ref_x + scl_devx, scl_ref_y + scl_devy),
                               (0, 0, 255),
                               line_thickness,
                               tipLength=0.2)
            except:
                pass

        else:   # Both target and deviation are valid

            # Scale image
            scl_target_x = int(target_x * self.out_scale)
            scl_target_y = int(target_y * self.out_scale)
            scl_target_radius = int(target_radius * self.out_scale)

            # Draw deviation Arrow
            cv.arrowedLine(img,
                           (scl_ref_x, scl_ref_y),
                           (scl_target_x, scl_target_y),
                           (0, 255, 0),
                           line_thickness,
                           tipLength=0.2)

            # Draw horizontal line
            cv.line(img,
                    (scl_target_x - scl_target_radius, scl_target_y),
                    (scl_target_x + scl_target_radius, scl_target_y),
                    line_color,
                    line_thickness)

            # Draw vertical line
            cv.line(img,
                    (scl_target_x, scl_target_y - scl_target_radius),
                    (scl_target_x, scl_target_y + scl_target_radius),
                    line_color,
                    line_thickness)

            # Draw the circle
            cv.circle(img,
                      (scl_target_x, scl_target_y),
                      scl_target_radius,
                      line_color,
                      line_thickness)

        if self.overlay:
            # Put white information bar

            if None not in deviation:
                deviation = (f"{deviation[0]:.2f}", f"{deviation[1]:.2f}")

            if None not in (target_x, target_y):
                target_x = f"{target_x:.2f}"
                target_y = f"{target_y:.2f}"

            bar_text = (f"Target at {target_x}, {target_y}; Deviation: {deviation[0]}, "
                        f"{deviation[1]};\n{handover_value}")

            # Define the height of the black bar (you can adjust this value)
            bar_height = int(height * 0.2)

            # Create a black bar

            bar = np.ones((bar_height, width, 3), dtype=np.uint8) * 255

            # Add the text to the black bar
            font = cv.FONT_HERSHEY_SIMPLEX

            text_lines = bar_text.split('\n')
            thickness = line_thickness

            # Put info text
            font_scale = 0.5
            text_position = 20
            for line in text_lines:
                cv.putText(bar, line, (5, text_position), font,
                           font_scale, (0, 0, 0), thickness, cv.LINE_AA)
                text_position += 20

            # Stack the black bar on top of the original image
            # If Moon would be under the bar at the bottom, put bar on top
            if target_x is None or deviation[0] is None:
                img[height-bar_height:height, 0:width] = bar
            elif (scl_target_y + scl_target_radius) > (height - bar_height):
                img[0:bar_height, 0:width] = bar
            else:
                img[height-bar_height:height, 0:width] = bar

        return img

    def moonposition(self, processed_img):
        """
        Calculates position of the Moon from image
        Output: target_x, target_y, radius

        """
        circles = cv.HoughCircles(
            processed_img,       # Input image
            cv.HOUGH_GRADIENT,   # Detection method
            dp=self.dp,       # Inverse ratio of the accumulator resolution to the image resolution
            minDist=processed_img.shape[0],          # Minimum distance between detected centers
            param1=self.param1,          # Higher threshold for edge detection
            param2=self.param2,           # Accumulator threshold for circle detection
            minRadius=int(self.minRadius * self.in_scale),        # Minimum circle radius 120
            maxRadius=int(self.maxRadius * self.in_scale)        # Maximum circle radius 160
        )

        if circles is not None:
            circles = np.uint16(np.around(circles))
            nr_circles = len(circles[0])
            circle = max(circles[0], key=lambda x: x[2])  # Filter out the biggest circle (moon)
            if nr_circles > 1:
                print(f"Number of circles detected: {nr_circles}. Used largest.")

            (center_x, center_y, radius) = (circle[0], circle[1], circle[2])

            return(center_x, center_y, radius)

        else:
            return(None, None, None)

    def get_deviation(self, target, ref):
        # Calculate deviation from two points

        if None in ref or None in target:
            return (None, None)

        else:
            target = (float(target[0]), float(target[1]))
            dev = (target[0] - ref[0], target[1] - ref[1])

            return dev


class log:
    def __init__(self, configuration):
        """
        Creates a dictionary to store the data logs and fills in the configuration parameters
        from the configuration-class
        """
        self.sheets = {}
        self.sheets["Target"] = []
        self.sheets["Activity"] = []
        self.sheets["Configuration"] = []
        self.deactivated = not(configuration.export_to_excel)

        # Log Config to excel
        self.add("Configuration", [configuration.profile, ""])
        for key in configuration.config[configuration.profile]:
            self.add("Configuration", [key, configuration.config[configuration.profile][key]])

    def add(self, sheetname, data):
        # Add data to existing sheet
        if self.deactivated:
            return
        if sheetname not in self.sheets:
            raise ValueError(f"Sheet {sheetname} does not exist.")
        else:
            self.sheets[sheetname].append(data)
        return

    def export(self):
        # Export data to excel file

        if self.deactivated:
            return
        # Generate standard file name
        filename = "log_" + time.strftime('%y-%m-%d_%H-%M', time.localtime())

        print(f"Nr. of Datapoints: {len(self.sheets['Target'])-1}")
        print(f"Config Profile: {self.sheets['Configuration'][0][0]}")
        temp = input(
            "Save Logged data as ...? Press Enter for default 'log_Y-M-D_H-M.xlsx', type 'n' or 'no' to skip. ")
        # Abort if no is name
        if temp:
            if temp in ["N", "n", "No", "NO", "nein", "Nein", "NEIN"]:
                print("Data has not been saved")
                return
            filename = temp

        # Input for note
        note = input("Add a Note. Press enter when done.\n")

        self.sheets['Configuration'].append([f'{time.ctime()}', ""])
        self.sheets['Configuration'].append(["NOTE", note + ""])

        df1 = pd.DataFrame(self.sheets["Target"])
        df2 = pd.DataFrame(self.sheets["Activity"])
        df3 = pd.DataFrame(self.sheets["Configuration"])

        # Write Excel file
        with pd.ExcelWriter(f"Logs/{filename}.xlsx", engine='openpyxl') as writer:
            df1.to_excel(writer, sheet_name='Target', index=False, header=False)
            df2.to_excel(writer, sheet_name='Activity', index=False, header=False)
            df3.to_excel(writer, sheet_name='Configuration', index=False, header=False)
        print(f"Exported to Excelfile '{filename}.xlsx'")


class buffer:
    def __init__(self, buffer_length=1):
        # Initiate dict for buffer values
        self.values = {}
        self.values['target_x'] = []
        self.values['target_y'] = []
        self.values['target_radius'] = []

        self.buffer_length = buffer_length

    def errorcheck(self, name=None):
        # Check if name exists in dict
        if name not in self.values:
            raise ValueError(f"Target '{name}' does not exist in the buffer.")

    def get_valid(self, name="target_x"):
        # returns string as information about valid values in buffer
        temp = 0

        if name is not None:
            self.errorcheck(name)
            temp = len([value for value in self.values[name] if value is not None])

        return f"{temp}/{self.buffer_length}"

    def add(self, value, name=None):
        # Add new value to buffer

        self.errorcheck(name)

        self.values[name].append(value)

        if self.buffer_length is not None and len(self.values[name]) > self.buffer_length:
            self.values[name].pop(0)

    def average(self, name):
        # return average of all values in buffer

        self.errorcheck(name)

        if not self.values[name]:
            return None
        temp = list(filter(lambda x: x is not None, self.values[name]))

        return float(sum(temp) / len(temp)) if temp else None

    def clear_all(self):
        # clear buffer values
        self.values['target_x'] = []
        self.values['target_y'] = []
        self.values['target_radius'] = []

# Test
