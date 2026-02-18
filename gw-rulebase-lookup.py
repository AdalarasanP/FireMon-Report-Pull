#!/usr/bin/env python3
###############################################################################
# gw-rulebase-lookup.py
#
# Runs locally on your workstation — SSHs into the MDS/CMA (Expert mode),
# executes mgmt_cli commands remotely, and processes output locally.
#
# Flow:
#   1. Prompts for MDS server IP, SSH user (admin), SSH password
#   2. Prompts for Domain name, Policy name
#   3. SSHs in via paramiko (Expert mode)
#   4. Queries all gateway/cluster objects, presents a pick-list
#   5. Runs rulebase lookup with install-on filter
#   6. Prints summary — output tee'd to a timestamped local log
#
# Prerequisites: pip install paramiko
###############################################################################

import sys
import json
import getpass
import datetime
import paramiko


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

class Logger:
    """Write to both stdout and a log file."""

    def __init__(self, logfile):
        self.logfile = open(logfile, "w", encoding="utf-8")

    def log(self, msg=""):
        print(msg)
        self.logfile.write(msg + "\n")
        self.logfile.flush()

    def close(self):
        self.logfile.close()


def ssh_connect(host, user, password):
    """Establish an SSH connection and return the paramiko client."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[*] Connecting to {host} as {user} …")
    client.connect(hostname=host, username=user, password=password, timeout=30)
    print(f"[+] Connected to {host}")
    return client


def ssh_exec(client, command, timeout=120):
    """Execute a command over SSH and return stdout as a string."""
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code


def run_mgmt_cli(client, domain, api_cmd, extra_args="", timeout=120):
    """Run an mgmt_cli command remotely with -r true -d <domain>."""
    cmd = f"mgmt_cli -r true -d {domain} {api_cmd} {extra_args} --format json"
    out, err, rc = ssh_exec(client, cmd, timeout=timeout)
    if rc != 0 and not out.strip():
        raise RuntimeError(f"mgmt_cli failed (rc={rc}): {err.strip()}")
    return out


def query_gateways_and_servers(client, domain):
    """Paginated query using show gateways-and-servers. Returns list of dicts."""
    results = []
    offset = 0
    batch = 500
    total = 1

    while offset < total:
        raw = run_mgmt_cli(
            client, domain, "show gateways-and-servers",
            f"limit {batch} offset {offset} details-level standard"
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            break

        if offset == 0:
            total = data.get("total", 0)
            if total == 0:
                break

        for obj in data.get("objects", []):
            results.append({
                "name": obj.get("name", ""),
                "uid": obj.get("uid", ""),
                "type": obj.get("type", ""),
            })

        offset += batch

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print("###############################################################")
    print("#  Gateway Rulebase Install-On Lookup  (Python / paramiko)    #")
    print("###############################################################")
    print()

    # ── Prompt: connection details ────────────────────────────────────────
    ssh_host = input("  MDS/CMA Server IP or Hostname : ").strip()
    ssh_user = input("  SSH Username                  : ").strip()
    ssh_pass = getpass.getpass("  SSH Password                  : ")
    print()

    # ── Prompt: domain & policy ───────────────────────────────────────────
    domain = input("  Domain (CMA) name             : ").strip()
    policy = input("  Access-layer / Policy name     : ").strip()
    limit_str = input("  Rulebase limit [500]           : ").strip()
    limit = int(limit_str) if limit_str else 500
    print()

    # ── Log file ──────────────────────────────────────────────────────────
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    logfile = f"gw-rulebase-lookup_{domain}_{ts}.log"
    log = Logger(logfile)

    log.log("================================================================")
    log.log(f"  Log started : {datetime.datetime.now()}")
    log.log(f"  Server      : {ssh_host}")
    log.log(f"  Domain      : {domain}")
    log.log(f"  Policy      : {policy}")
    log.log("================================================================")
    log.log()

    # ── SSH connect ───────────────────────────────────────────────────────
    try:
        client = ssh_connect(ssh_host, ssh_user, ssh_pass)
    except Exception as e:
        log.log(f"[!] SSH connection failed: {e}")
        log.close()
        sys.exit(1)

    try:
        # ── Step 1: Collect all gateways & clusters ───────────────────────
        log.log("============================================================")
        log.log(f"  Querying domain: {domain}")
        log.log("  Collecting gateways & servers (show gateways-and-servers) …")
        log.log("============================================================")
        log.log()

        try:
            gw_list = query_gateways_and_servers(client, domain)
        except RuntimeError as e:
            log.log(f"  [!] show gateways-and-servers failed: {e}")
            gw_list = []

        if not gw_list:
            log.log(f"[!] No gateways or clusters found in domain '{domain}'.")
            log.close()
            sys.exit(1)

        log.log(f"Found {len(gw_list)} gateway/cluster objects.")
        log.log()

        # ── Step 2: Display numbered pick-list ────────────────────────────
        header = f"{'#':<5}  {'NAME':<45}  {'UID':<38}  {'TYPE'}"
        sep    = f"{'---':<5}  {'—'*45:<45}  {'—'*38:<38}  {'—'*16}"

        while True:
            log.log(header)
            log.log(sep)

            for idx, gw in enumerate(gw_list, start=1):
                line = f"{idx:<5}  {gw['name']:<45}  {gw['uid']:<38}  {gw['type']}"
                log.log(line)

            log.log()
            log.log(f"  0  =  EXIT")
            log.log()

            # ── Step 3: Prompt user to choose ─────────────────────────────
            while True:
                choice = input(f"Select a gateway/cluster by number (1-{len(gw_list)}) or 0 to exit: ").strip()
                if choice == "0":
                    break
                if choice.isdigit() and 1 <= int(choice) <= len(gw_list):
                    break
                print("  Invalid choice. Try again.")

            if choice == "0":
                log.log("[*] User chose to exit.")
                break

            selected = gw_list[int(choice) - 1]
            sel_name = selected["name"]
            sel_uid  = selected["uid"]
            sel_type = selected["type"]

            log.log()
            log.log("------------------------------------------------------------")
            log.log(f"  Selected : {sel_name}")
            log.log(f"  UID      : {sel_uid}")
            log.log(f"  Type     : {sel_type}")
            log.log("------------------------------------------------------------")
            log.log()

            # ── Step 4: Fetch the rulebase (paginated, with filter) ───────
            log.log(f'Fetching rulebase for policy: {policy} (filter: install-on:"{sel_name}") …')

            all_rules = []
            object_dict = {}
            offset = 0
            total_rules = 1
            first = True

            while offset < total_rules:
                raw = run_mgmt_cli(
                    client, domain, "show access-rulebase",
                    f'name "{policy}" filter "install-on:\\"{sel_name}\\"" '
                    f'limit {limit} offset {offset} '
                    f'details-level standard use-object-dictionary true',
                    timeout=180,
                )

                try:
                    page = json.loads(raw)
                except json.JSONDecodeError:
                    log.log(f"[!] Failed to parse rulebase JSON at offset {offset}")
                    break

                if first:
                    total_rules = page.get("total", 0)
                    first = False
                    if total_rules == 0:
                        log.log(f"[!] Rulebase '{policy}' returned 0 rules.")
                        break
                    log.log(f"  Total rules in policy: {total_rules}")

                # Collect object-dictionary entries
                for obj in page.get("objects-dictionary", []):
                    object_dict[obj.get("uid", "")] = obj.get("name", obj.get("uid", ""))

                # Collect rulebase entries (handle sections)
                for entry in page.get("rulebase", []):
                    if entry.get("type") == "access-section":
                        for rule in entry.get("rulebase", []):
                            if rule.get("type") == "access-rule":
                                all_rules.append(rule)
                    elif entry.get("type") == "access-rule":
                        all_rules.append(entry)

                returned_to = page.get("to", 0)
                offset = returned_to

            log.log()

            # ── Step 5: Find rules where install-on contains the selected UID
            matched = []
            for rule in all_rules:
                install_on_uids = rule.get("install-on", [])
                if sel_uid in install_on_uids:
                    matched.append(rule)

            # ── Step 6: Print summary ─────────────────────────────────────
            log.log("============================================================")
            log.log("  INSTALL-ON LOOKUP SUMMARY")
            log.log("============================================================")
            log.log()
            log.log(f"  Gateway/Cluster : {sel_name}")
            log.log(f"  UID             : {sel_uid}")
            log.log(f"  Type            : {sel_type}")
            log.log(f"  Policy          : {policy}")
            log.log(f"  Domain          : {domain}")
            log.log()
            log.log(f"  Rules matched   : {len(matched)}")
            log.log()

            if matched:
                log.log(f"  {'RULE #':<12}  {'RULE UID':<38}  INSTALL-ON TARGETS")
                log.log(f"  {'--------':<12}  {'—'*38:<38}  {'—'*30}")
                for rule in matched:
                    rnum = rule.get("rule-number", "N/A")
                    ruid = rule.get("uid", "")
                    install_names = [
                        object_dict.get(u, u) for u in rule.get("install-on", [])
                    ]
                    log.log(f"  {str(rnum):<12}  {ruid:<38}  {', '.join(install_names)}")

            log.log()
            log.log("============================================================")
            log.log("  Done.")
            log.log("============================================================")

            # ── Step 7: Generate removal command list ─────────────────────
            if matched:
                ts_cmd = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_name = sel_name.replace(" ", "_").replace("/", "_")
                cmd_file = f"remove-install-on_{safe_name}_{domain}_{ts_cmd}.txt"

                with open(cmd_file, "w", encoding="utf-8", newline="\n") as cf:
                    cf.write(f"# REMOVE '{sel_name}' FROM INSTALL-ON\n")
                    cf.write(f"# Domain  : {domain}\n")
                    cf.write(f"# Policy  : {policy}\n")
                    cf.write(f"# Gateway : {sel_name} (UID: {sel_uid})\n")
                    cf.write(f"# Rules   : {len(matched)}\n")
                    cf.write(f"# Generated: {datetime.datetime.now()}\n")
                    cf.write(f"#\n")
                    cf.write(f"# LOOKUP COMMANDS USED:\n")
                    cf.write(f"# mgmt_cli -r true -d {domain} show gateways-and-servers limit 500 details-level standard --format json\n")
                    cf.write(f'# mgmt_cli -r true -d {domain} show access-rulebase name "{policy}" filter \'install-on:"{sel_name}"\' limit 500 details-level standard use-object-dictionary true --format json\n')
                    cf.write(f"#\n")
                    cf.write(f"# STEP 1: LOGIN (writes session to file 'id')\n")
                    cf.write(f'mgmt_cli login user <USERNAME> password <PASSWORD> domain "{domain}" read-only false --format json >> id\n')
                    cf.write(f"#\n")
                    cf.write(f"# STEP 2: REMOVAL COMMANDS (using session file 'id')\n\n")

                    for i, rule in enumerate(matched, start=1):
                        rnum = rule.get("rule-number", "N/A")
                        ruid = rule.get("uid", "")
                        install_names = [
                            object_dict.get(u, u) for u in rule.get("install-on", [])
                        ]
                        remaining = [n for n in install_names if n != sel_name]

                        cf.write(f"# Rule #{rnum} | Current install-on: {', '.join(install_names)} | After: {', '.join(remaining) if remaining else 'NONE'}\n")
                        cf.write(f'mgmt_cli -s id set access-rule uid "{ruid}" layer "{policy}" install-on.remove "{sel_name}" --format json\n\n')

                    cf.write(f"# STEP 3: PUBLISH (run once after all removals)\n")
                    cf.write(f"mgmt_cli -s id publish --format json\n\n")
                    cf.write(f"# STEP 4: LOGOUT\n")
                    cf.write(f"mgmt_cli -s id logout --format json\n")

                log.log()
                log.log(f"  Command list generated : {cmd_file}")
                log.log(f"  Total removal commands : {len(matched)}")
                log.log()
                print(f"\n  >>> Command list saved to: {cmd_file}")

            log.log()
            log.log("============================================================")
            log.log()

        log.log("============================================================")
        log.log("  Session complete.")
        log.log("============================================================")

    finally:
        client.close()
        log.log()
        log.log("================================================================")
        log.log(f"  Log ended : {datetime.datetime.now()}")
        log.log(f"  Log saved to: {logfile}")
        log.log("================================================================")
        log.close()
        print(f"\n  Log saved to: {logfile}")


if __name__ == "__main__":
    main()
