#!/usr/bin/python3

# Collect image and proximity data from Vector.

import anki_vector
import logging
import pickle
import sqlite3
import time

SCHEMA = r"""CREATE TABLE IF NOT EXISTS vector_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image       BLOB NOT NULL,
    prox        REAL NOT NULL
)
"""


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
    pickled = read_image(robot)
    prox = robot.proximity.last_sensor_reading.distance.distance_mm
    print("prox: ", prox)
    conn.execute("INSERT INTO vector_data (image, prox) VALUES (?, ?)", (pickled, prox))


def get_robot():
    robot = anki_vector.Robot(
        default_logging=False, enable_vision_mode=True, enable_camera_feed=True
    )
    robot.connect()
    return robot


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


def try_collecting(conn):
    logging.info("connecting to vector")
    try:
        robot = get_robot()
    except anki_vector.exceptions.VectorControlException:
        if robot:
            robot.disconnect()
        print("failed to connect... will try again in an hour.")
        time.sleep(3600)
        return

    # This sleep is needed to give the SDK time to get sensor readings and
    # the status ready. This is an arbitrary choice of timeout that seems to
    # work.
    time.sleep(0.25)
    battery_state = robot.get_battery_state()
    if battery_state:
        print("battery voltage: {0}".format(battery_state.battery_volts))

    print("connected!")
    sleep = 30
    if should_read_sensors(robot):
        print("collecting sensor data")
        collect(robot, conn)
        conn.commit()
        print("letting vector roam around")
    else:
        sleep = 600
        print("vector isn't ready yet")

    robot.disconnect()
    logging.debug("Sleeping for {} seconds".format(sleep))
    time.sleep(sleep)


def main(logger=None):
    if not logger:
        logger = logging.getLogger()
    # add a console logger
    logger.addHandler(logging.StreamHandler())

    conn = sqlite3.connect("vector.db")
    conn.execute(SCHEMA)

    while True:
        try:
            try_collecting(conn)
        finally:
            time.sleep(60)  # time for the error to clear up


if __name__ == "__main__":
    logging.basicConfig(filename="vector.log", level=logging.DEBUG)
    logger = logging.getLogger()
    main(logger)
