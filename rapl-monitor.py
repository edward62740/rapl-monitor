import rapl
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.exceptions import InfluxDBError
import sched

update_frequency = 5

# Initialize InfluxDB client
bucket = ""
org = ""
token = ""
# Store the URL of your InfluxDB instance
url = ""
prev_sample = None
selfname = "SERVER"


class BatchingCallback(object):

    def success(self, conf: (str, str, str), data: str):
        """Successfully writen batch."""
        print(f"Written batch: {conf}, data: {data}")

    def error(self, conf: (str, str, str), data: str, exception: InfluxDBError):
        """Unsuccessfully writen batch."""
        print(f"Cannot write batch: {conf}, data: {data} due: {exception}")

    def retry(self, conf: (str, str, str), data: str, exception: InfluxDBError):
        """Retryable error."""
        print(f"Retryable error occurs for batch: {conf}, data: {data} retry: {exception}")


def main_task(sc):
    now_sample = rapl.RAPLMonitor.sample()
    global prev_sample
    delta = now_sample - prev_sample
    prev_sample = now_sample
    pt = []
    for d in delta.domains:
        domain = delta.domains[d]
        power = delta.average_power(package=domain.name)
        pt.append(Point(selfname).tag("domain", domain.name).field("power", power))

        for sd in domain.subdomains:
            subdomain = domain.subdomains[sd]
            power = delta.average_power(package=domain.name, domain=subdomain.name)
            pt.append(Point(selfname).tag("domain", subdomain.name).field("power", power))

    with InfluxDBClient(url=url, token=token, org=org) as client:
        with client.write_api(success_callback=callback.success,
                              error_callback=callback.error,
                              retry_callback=callback.retry) as write_api:
            write_api.write(bucket=bucket, record=pt)
    sc.enter(update_frequency, 1, main_task, (sc,))


if __name__ == "__main__":
    callback = BatchingCallback()
    s = sched.scheduler(time.time, time.sleep)
    prev_sample = rapl.RAPLMonitor.sample()
    s.enter(update_frequency, 1, main_task, (s,))
    s.run()
