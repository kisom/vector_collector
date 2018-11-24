#!/usr/bin/env python3.6

# Collect image and proximity data from Vector.

import anki_vector
import logging
import pickle
import random
import sqlite3
import sys
import time
import traceback

SCHEMA = r"""CREATE TABLE IF NOT EXISTS vector_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image       BLOB NOT NULL,
    prox        REAL NOT NULL
)
"""


def get_database_conn(path="vector.db"):
    conn = sqlite3.connect("vector.db")
    conn.execute(SCHEMA)
    return conn


def prob_say(robot, p, text):
    if random.random() <= p:
        robot.say_text(text)


def read_image(robot):
    while not robot.camera.latest_image:
        time.sleep(0.1)
    with open("latest_image", "wb") as image_file:
        image = robot.camera.latest_image.tobytes()
        image_file.write(image)
        return image


def collect(robot, conn):
    while not robot.proximity.last_sensor_reading:
        print("waiting for prox sensor")
        time.sleep(1)
    image = read_image(robot)
    if len(image) != 691200:
        logging.error(
            "image size of {} does not match expected size of {}".format(len(image))
        )
        return
    prox = robot.proximity.last_sensor_reading.distance.distance_mm
    print("prox: ", prox)
    conn.execute("INSERT INTO vector_data (image, prox) VALUES (?, ?)", (image, prox))


def should_read_sensors(robot):
    if not robot.status:
        print("Vector's status isn't available")
        return False
    if robot.status & 0x1000 != 0:
        print("Vector is on his charger")
        return False
    if robot.status & 0x2000 != 0:
        print("Vector is charging")
        return False
    return True


def try_collecting(conn, robot):
    logging.info("connecting to vector")
    delay = collector(conn, robot)
    logging.debug(
        "{} sleeping for {} seconds".format(
            time.strftime("%Y-%d-%m %H:%M:%S %z"), delay
        )
    )
    time.sleep(delay)


def collector(conn, robot):

    # This sleep is needed to give the SDK time to get sensor readings and
    # the status ready. This is an arbitrary choice of timeout that seems to
    # work.
    print("getting robot state")
    time.sleep(0.25)
    battery_state = robot.get_battery_state()
    if battery_state:
        print("battery voltage: {0}".format(battery_state.battery_volts))

    print("connected!")
    sleep = 1
    if should_read_sensors(robot):
        print("collecting sensor data")
        collect(robot, conn)
        conn.commit()
        print("letting vector roam around")
    else:
        sleep = 180
        prob_say(robot, 0.05, "I'm still charging.")
        print("vector isn't ready yet")

    return sleep


def main(logger=None):
    if not logger:
        logger = logging.getLogger()
    # add a console logger
    logger.addHandler(logging.StreamHandler())

    conn = get_database_conn()
    while True:
        with anki_vector.Robot(
            default_logging=False,
            enable_vision_mode=True,
            enable_camera_feed=True,
            requires_behavior_control=False,
        ) as robot:
            try:
                try_collecting(conn)
            except Exception as esc:
                logging.debug(
                    "exception while trying collect:\n{}\n{}".format(
                        esc, traceback.format_exc()
                    )
                )
                print(esc)
            finally:
                time.sleep(60)  # time for the error to clear up


def count_records():
    conn = get_database_conn()
    result = conn.execute("select count(*) from vector_data")
    print(result.fetchall()[0][0])


if __name__ == "__main__":
    if len(sys.argv) == 2:
        if sys.argv[1] == "count":
            count_records()
            sys.exit(0)
    logging.basicConfig(filename="vector.log", level=logging.DEBUG)
    logger = logging.getLogger()
    main(logger)
