from math import (
    cos,
    sin
)
import bpy
from time import perf_counter
from sys import stdout


# prints out a progress bar of a job and a series of sub-jobs to the console, and uses Blender's window manager to show
# the jobs total progress at the cursor
class ProgressReporter:
    def __init__(self, job, sub_jobs, sub_job_totals):
        self.job_total = sum(sub_job_totals)
        self.sub_job_totals = sub_job_totals
        self.job_progress = 0
        self.sub_job_progress = 0

        self.sub_jobs = sub_jobs
        self.current_sub_job = None

        self.update_rate = 0.1
        self.update_timer = perf_counter()
        self.job_timer = None

        self.name_len = len(max(self.sub_jobs, key=len))
        self.bar_len = 20
        self.line_len = self.name_len + self.bar_len + 37

        # used to adjust the length of the tittle line for visual alignment
        if len(job) % 2 == self.line_len % 2:
            corrector = 0
        else:
            corrector = 1

        # start the widow manager progress indicator
        self.wm = bpy.context.window_manager
        self.wm.progress_begin(0, 100)

        print(
            f"{'-' * int(((self.line_len - len(job) - 2) / 2))} "
            f"{job} "
            f"{'-' * (int(((self.line_len - len(job) - 2) / 2)) + corrector)}"
        )

    # used to initiate sub-jobs
    def start_sub_job(self):
        # get the current_sub_job, will move on to the next job every time this function is called
        if self.current_sub_job is None:
            self.current_sub_job = self.sub_jobs[0]
        else:
            self.current_sub_job = self.sub_jobs[self.sub_jobs.index(self.current_sub_job) + 1]

        # reset the sub_job_progress and the timer
        self.sub_job_progress = 0
        self.job_timer = perf_counter()

        # start the progress bar at 0%
        stdout.write(
            f"{self.current_sub_job}"
            f"{' ' * (5 + (self.name_len - len(self.current_sub_job)))}"
            f"{self.sub_jobs.index(self.current_sub_job) + 1:02d}/{len(self.sub_jobs):02d} "
            f"[{' ' * self.bar_len}] 000%"
        )
        stdout.flush()

    # used to update the console print-out and the window manager
    def update(self):
        # update the progress variables
        self.job_progress += 1
        self.sub_job_progress += 1

        # check if the time elapsed since last update exceeds the update rate
        if perf_counter() - self.update_timer > self.update_rate:

            # reset the update_timer
            self.update_timer = perf_counter()

            # calculate the progress of the current sub-job and the total progress of the job
            progress = self.sub_job_progress / self.sub_job_totals[self.sub_jobs.index(self.current_sub_job)]
            total_progress = self.job_progress / self.job_total

            # update the window manager and rewrite the console printout with the current progress of the sub-job
            self.wm.progress_update(int(total_progress * 100))
            stdout.write(
                f"\r{self.current_sub_job}"
                f"{' ' * (5 + (self.name_len - len(self.current_sub_job)))}"
                f"{self.sub_jobs.index(self.current_sub_job) + 1:02d}/{len(self.sub_jobs):02d} "
                f"[{'#' * int(progress * self.bar_len)}"
                f"{' ' * (self.bar_len - (int(progress * self.bar_len)))}] "
                f"{int(progress * 100):03d}%"
            )
            stdout.flush()

    # used to finalise the console printout and, if on the last job, the window manager
    def end_sub_job(self):
        # print the progress bar a 100%
        print(
            f"\r{self.current_sub_job}"
            f"{' ' * (5 + (self.name_len - len(self.current_sub_job)))}"
            f"{self.sub_jobs.index(self.current_sub_job) + 1:02d}/{len(self.sub_jobs):02d} "
            f"[{'#' * self.bar_len}] 100%"
            f"{' ' * 5}"
            f"DONE in {perf_counter() - self.job_timer:05.2f}s"
        )

        # check if the current sub-job is the last job
        # if so, end the window manager progress and print the job separator line
        if self.sub_jobs.index(self.current_sub_job) + 1 == len(self.sub_jobs):
            self.wm.progress_end()
            print(
                f"{'-' * self.line_len}"
            )

    # uses the elapsed time of a job to estimate the amount of time a job will take
    def _estimate_job_time(self):
        # return none if no progress has been made
        if self.job_progress == 0:
            return None

        elapsed_time = perf_counter() - self.job_timer
        estimated_total_time = (self.job_total / self.job_progress) * elapsed_time
        return estimated_total_time

    # returning the progress of a process adds a significant amount of time to longer processes
    # the longer the process the more time is added by progress reporting
    # to mitigate this, this function will change the update_rate of the instance based on how long the job is
    # estimated to take, reducing the number of times progress is reported
    def adjust_update_rate(self):
        estimated_total_time = self._estimate_job_time()
        if estimated_total_time is not None:
            # Adjust the update rate based on the estimated total time
            self.update_rate = max(estimated_total_time / 100, 0.1)


# calculates the position of a 2d coordinate after being rotated around a point
def rotate_around_point(coordinate, angle, point=(0, 0)):
    x, y = coordinate[0] - point[0], coordinate[1] - point[1]
    cos_theta, sin_theta = cos(angle), sin(angle)
    return x * cos_theta - y * sin_theta + point[0], y * cos_theta + x * sin_theta + point[1]


# check if an object can be exported by the plugin
def is_exportable_object(obj):
    object_types = ['MESH']
    # only include armatures if Godot version is 3.1 or later
    if int(bpy.context.scene.godot_2d_bridge_tools.godot_version) > 2:
        object_types += ['ARMATURE']
    return (
        obj.gd2db_object_2d and obj.visible_get() and
        any(obj.type == x for x in object_types)
    )


# returns a generator of objects to be exported by the plugin
def export_objects():
    # check if the user wants to export all exportable objects in the scene or only currently selected objects
    if bpy.context.scene.godot_2d_bridge_tools.selected:
        exportable_objects = (
            obj for obj in bpy.context.selected_objects if is_exportable_object(obj)
        )
    else:
        exportable_objects = (
            obj for obj in bpy.context.scene.objects if is_exportable_object(obj)
        )
    return exportable_objects


# creates a popup based on it's arguments
def custom_message_box(message="", title="Message Box", icon='INFO'):
    def draw(self, _context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
