import time


def wait(c):
    for _ in range(200):
        r = c.get("/api/state").json()["runs"][0]
        if r["status"] != "running":
            return r
        time.sleep(0.01)
    raise AssertionError("run did not settle")
