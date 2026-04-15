import requests


class ProxyChecker:

    IP_JSON  = "https://api.ipify.org?format=json"
    IP_PLAIN = "https://ifconfig.io/ip"

    def check(self, proxy_url: str, timeout: float = 8.0) -> tuple[bool, str]:
        proxies = {"http": proxy_url, "https": proxy_url}
        err_json = ""
        try:
            r = requests.get(self.IP_JSON, proxies=proxies, timeout=timeout)
            r.raise_for_status()
            ip = r.json().get("ip", "").strip()
            if ip:
                return True, ip
            err_json = "empty-json-ip"
        except requests.RequestException as e:
            err_json = f"{type(e).__name__}: {e}"

        try:
            r = requests.get(self.IP_PLAIN, proxies=proxies, timeout=timeout)
            r.raise_for_status()
            ip = r.text.strip()
            if ip:
                return True, ip
            return False, "empty-plain-ip"
        except requests.RequestException as e:
            return False, f"{err_json} | {type(e).__name__}: {e}"