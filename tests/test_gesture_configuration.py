import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
def original(name):
    files={"keyboard.toml":"pre-gesture-keyboard.toml","vial.json":"pre-gesture-vial.json"}
    return (ROOT/"tests/fixtures"/files[name]).read_bytes()


class ConfigurationTests(unittest.TestCase):
    def test_existing_configuration_preserved(self):
        old = tomllib.loads(original("keyboard.toml").decode())
        new = tomllib.loads((ROOT / "keyboard.toml").read_text())
        sensor=old['split']['central']['input_device']['pmw3610'][0]
        sensor['invert_x']=True
        sensor['invert_y']=not True
        # The stock fixture leaves invert_x unspecified, which is false.
        old['keyboard']['name']=old['keyboard']['product_name']=new['keyboard']['name']
        old['host'].update(vial_enabled=True,rynk_enabled=False)
        old['rmk']['fork_max_num']=32
        old['split']['central']['battery_user_description']='Right'
        old['split']['peripheral'][0].update(battery_adc_pin='P0_31',adc_divider_measured=510,adc_divider_total=1510,battery_user_description='Left')
        new_sensor=new['split']['central']['input_device']['pmw3610'][0]
        new_sensor.setdefault('invert_x',False)
        for section in old.keys() - {"layout", "layer", "behavior", "event"}:
            self.assertEqual(new[section],old[section],section)
        self.assertEqual(new["layout"]["rows"], 5)
        for name in old["layout"].keys() - {"rows", "matrix_map", "layers"}:
            self.assertEqual(new["layout"][name], old["layout"][name])
        positions = lambda s: re.findall(r"\(\d+,\d+\)", s)
        self.assertEqual(positions(new["layout"]["map"]), positions(old["layout"]["matrix_map"]) + [f"(4,{c})" for c in range(11)] + ["(0,5)"])
        for layer, (before, after) in enumerate(zip(old["layer"], new["keymap"]["layer"])):
            for name in before.keys() - {"keys", "encoders"}:
                self.assertEqual(before[name], after[name])
        self.assertEqual(len(new["keymap"]["layer"]), 8)
        baseline=json.loads((ROOT/"tests/fixtures/verified-sha256.json").read_text())
        for name in ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "src/peripheral.rs", "memory.x"]:
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),baseline[name],name)
        # Wrapper mirrors these *processor* defaults; hardware inversion is untouched.
        sensor = new["split"]["central"]["input_device"]["pmw3610"][0]
        for name in ["proc_invert_x", "proc_invert_y", "proc_swap_xy"]:
            self.assertFalse(sensor.get(name, False))
        self.assertEqual(new["event"]["keyboard"], {"pubs": 3, "subs": 4})

    def test_vial_coordinates_and_custom_codes_preserved(self):
        old = json.loads(original("vial.json"))
        new = json.loads((ROOT / "vial.json").read_text())
        self.assertEqual([x["name"] for x in new["customKeycodes"][9:]], ["CLR_PEER", "GT1", "GT2", "GT3", "ST"])
        self.assertEqual(new["matrix"], {"rows": 5, "cols": 11})
        self.assertEqual(new["customKeycodes"][:9], old["customKeycodes"])
        self.assertEqual(new["layouts"]["keymap"][:-3], old["layouts"]["keymap"])
        added = [item for row in new["layouts"]["keymap"][-3:] for item in row if isinstance(item, str)]
        self.assertCountEqual(added, [f"4,{c}" for c in range(11)] + ["0,5"])

    def test_all_tasks_are_awaited_and_original_motion_is_not_run_twice(self):
        source = (ROOT / "src/central.rs").read_text()
        self.assertIn("#[Overwritten(entry)]", source)
        expected = {"adc_device", "trackball0_id0_device", "matrix", "storage", "keyboard", "trigger_monitor", "usb_transport", "ble_transport", "wpm_processor", "watchdog_runner", "battery_processor", "trackball0_id0_processor"}
        match = re.search(r"rmk::run_all!\((.*?)\)\s*\.await", source, re.S)
        self.assertIsNotNone(match, "A dropped run_all future would disable all core tasks")
        tasks = re.findall(r"\b\w+\b", match[1])
        self.assertEqual(set(tasks), expected)
        self.assertEqual(len(tasks), len(expected))
        self.assertLess(tasks.index("trigger_monitor"), tasks.index("trackball0_id0_processor"))
        self.assertIn("PeripheralMatrixConfig",source)
        self.assertIn(".with_host_service(&host_service)",source)
        self.assertIn("BleTransport::new",source)


if __name__ == "__main__":
    unittest.main()
