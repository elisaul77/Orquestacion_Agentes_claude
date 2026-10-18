"""Visible symptom check for the bug2-orch proof (competition/seed/proof). Never mounted into runs.

The user's report: links between my containers show up as external or host. This is the check the
report implies. It reuses the hidden fixture (same fake /proc, same docker client) so both checks see
identical data. BUG2_HIDDEN points at competition/hidden/test_bug2_hidden.py.
"""
import importlib.util
import os

_spec = importlib.util.spec_from_file_location("bug2_hidden", os.environ["BUG2_HIDDEN"])
_hidden = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hidden)
netmap = _hidden.netmap            # fixtures re-exported: pytest discovers them in this module
proc_and_client = _hidden.proc_and_client


def test_symptom_no_link_between_my_containers_is_external_or_host(netmap, proc_and_client):
    edges = netmap.collect(proc_and_client)["edges"]
    names = {"kunna-frontend", "kunna-backend"}
    wrong = [e for e in edges if e["kind"] in ("external", "host")
             and (e["source"] in names or e["target"] in names)]
    assert wrong == [], wrong
