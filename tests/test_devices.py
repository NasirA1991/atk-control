"""Capability and model database tests."""

from __future__ import annotations

import unittest

from atk_control import devices, protocol


class ModelTests(unittest.TestCase):
    def test_mad_r_identity(self) -> None:
        model = devices.model_for(2, 49, 0x373B, 0x1040)
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.name, "MAD R")
        self.assertEqual(model.sensor, "PAW3395")

    def test_r1_transport_resolution(self) -> None:
        model = devices.model_for(2, 12, 0x3554, 0xF58F, "VXE R1")
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.brand, "VXE")

    def test_r1_pro_identity_on_1k_receiver(self) -> None:
        model = devices.model_for(2, 8, 0x3554, 0xF58A, "Compx VXE NordicMouse 1K Dongle")
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.name, "VXE R1 Pro")
        receiver = devices.receiver_for(0xF58A, "Compx VXE NordicMouse 1K Dongle")
        self.assertIsNotNone(receiver)
        assert receiver is not None
        caps = devices.capabilities_for(model=model, receiver=receiver)
        self.assertEqual(caps.polling_rates, [125, 250, 500, 1000])
        self.assertEqual(caps.link_ceiling, 1000)

    def test_unknown_falls_back_to_usb(self) -> None:
        self.assertIsNone(devices.model_for(None, None, 0x373B, 0x9999))
        caps = devices.capabilities_for(model=None, receiver=None,
                                        sensor_name=None, usb_name="Compx Mystery Mouse")
        self.assertEqual(caps.name, "Mystery Mouse")

    def test_experimental_catalog_entry(self) -> None:
        model = devices.model_for(2, 36, 0x373B, 0x1014)
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.name, "ATK F1 Pro")
        self.assertEqual(model.sensor, "PAW3950")
        self.assertTrue(model.experimental)

    def test_core26k_sensor(self) -> None:
        sensor = devices.SENSORS["CORE26K"]
        self.assertEqual(sensor.min_dpi, 50)
        self.assertEqual(sensor.max_dpi, 26000)
        self.assertIn(26000, sensor.options())

    def test_a9_ultimate_identity(self) -> None:
        model = devices.model_for(1, 3, 0x373B, 0x11B6, "Compx ATK A9 Ultimate")
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.name, "ATK A9 Ultimate")
        self.assertEqual(model.brand, "ATK")
        # ATK HUB's model table lists this identity with a PAW3950Ultra.
        self.assertEqual(model.sensor, "PAW3950Ultra")
        self.assertEqual(model.sensor_profile.max_dpi, 42000)
        self.assertEqual(model.sensor_profile.family, "ultra")
        self.assertTrue(model.button_remap)
        self.assertFalse(model.experimental)
        self.assertIs(devices.MODEL_BY_USB[(0x373B, 0x11B6)], model)

    def test_vxe_r1_nk_is_a_separate_v2_identity(self) -> None:
        model = devices.v2_model_for(2, 8, 0x373B, 0x1216, "ATK NK mouse NANO dongle")
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.name, "VXE R1 NK")
        self.assertEqual(model.brand, "VXE")
        self.assertEqual(model.sensor, "PAW3395SE")
        self.assertEqual(model.max_polling, 1000)
        self.assertTrue(model.button_remap)
        self.assertTrue(model.normalizes_default_buttons)
        self.assertFalse(model.angle_supported)
        self.assertFalse(model.dpi_lighting)
        self.assertFalse(model.stage_colors)
        # CID/MID 2,8 is still the wired v1 R1 Pro in the older table.
        self.assertEqual(devices.MODEL_BY_CIDMID[(2, 8)].name, "VXE R1 Pro")

    def test_vxe_r1_nk_needs_identity_not_usb_id(self) -> None:
        # The NearLink receiver also answers for an R1 S NK (2,9).
        self.assertIsNone(
            devices.v2_model_for(2, 9, 0x373B, 0x1216, "ATK NK mouse NANO dongle")
        )
        self.assertIsNone(
            devices.v2_model_for(None, None, 0x373B, 0x1216, "ATK NK mouse NANO dongle")
        )


    def test_vxe_r1_se_plus_leaves_the_read_only_catalog(self) -> None:
        model = devices.model_for(2, 31, 0x373B, 0x1085, "CX Wireless mouse -1k dongle")
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.name, "VXE R1 SE+")
        self.assertEqual(model.sensor, "PAW3395SE")
        self.assertFalse(model.experimental)
        self.assertTrue(model.button_remap)
        self.assertNotIn(
            (2, 31), {(entry.cid, entry.mid) for entry in devices.EXPERIMENTAL_MODELS}
        )
        receiver = devices.receiver_for(0x1085, "CX Wireless mouse -1k dongle")
        self.assertIsNotNone(receiver)
        caps = devices.capabilities_for(model=model, receiver=receiver)
        self.assertEqual(caps.link_ceiling, 1000)
        self.assertEqual(caps.polling_rates, [125, 250, 500, 1000])
        self.assertEqual(caps.sensor.max_dpi, 18000)


class CapabilityTests(unittest.TestCase):
    def test_8k_receiver(self) -> None:
        model = devices.MODEL_BY_CIDMID[(2, 49)]
        receiver = devices.receiver_for(0x1040, "Compx MAD 8K DONGLE")
        caps = devices.capabilities_for(model=model, receiver=receiver)
        self.assertEqual(caps.link_ceiling, 8000)
        self.assertEqual(caps.polling_rates[-1], 8000)
        self.assertIn(4000, caps.polling_rates)

    def test_4k_receiver(self) -> None:
        receiver = devices.receiver_for(0x11A9, "Wireless mouse 4k dongle")
        self.assertIsNotNone(receiver)
        assert receiver is not None
        self.assertEqual(receiver.max_polling, 4000)

    def test_cable_is_one_kilohertz(self) -> None:
        model = devices.MODEL_BY_CIDMID[(2, 49)]
        caps = devices.capabilities_for(model=model, receiver=None)
        self.assertEqual(caps.link_ceiling, 1000)
        self.assertEqual(caps.polling_rates, [125, 250, 500, 1000])

    def test_a9_ultimate_cable_uses_its_reported_rate(self) -> None:
        model = devices.MODEL_BY_CIDMID[(1, 3)]
        caps = devices.capabilities_for(model=model, receiver=None, active_polling=4000)
        self.assertEqual(caps.link_ceiling, 4000)
        self.assertEqual(caps.polling_rates, [125, 250, 500, 1000, 2000, 4000])
        # The 8 kHz dongle is the only link that advertises 8000 Hz.
        dongle = devices.receiver_for(0x11D9, "Compx Wireless mouse 8k dongle-L")
        self.assertIsNotNone(dongle)
        assert dongle is not None
        caps = devices.capabilities_for(model=model, receiver=dongle, active_polling=4000)
        self.assertEqual(caps.link_ceiling, 8000)
        self.assertEqual(caps.polling_rates[-1], 8000)

    def test_vxe_r1_nk_receiver_ceiling(self) -> None:
        model = devices.V2_MODEL_BY_CIDMID[(2, 8)]
        receiver = devices.receiver_for(0x1216, "ATK NK mouse NANO dongle")
        self.assertIsNotNone(receiver)
        assert receiver is not None
        self.assertEqual(receiver.max_polling, 1000)
        caps = devices.capabilities_for(model=model, receiver=receiver)
        self.assertEqual(caps.link_ceiling, 1000)
        self.assertEqual(caps.polling_rates, [125, 250, 500, 1000])

    def test_vxe_4k_receiver(self) -> None:
        receiver = devices.receiver_for(0xF505, "Compx VGN Dragonfly 4K Receiver")
        self.assertIsNotNone(receiver)
        assert receiver is not None
        self.assertEqual(receiver.max_polling, 4000)
        self.assertIn("4K", receiver.name)
        model = devices.model_for(2, 8, 0x3554, 0xF505, "Compx VGN Dragonfly 4K Receiver")
        assert model is not None
        caps = devices.capabilities_for(model=model, receiver=receiver)
        self.assertEqual(caps.polling_rates, [125, 250, 500, 1000, 2000, 4000])

    def test_new_write_capabilities_are_gated_per_model(self) -> None:
        mad = devices.MODEL_BY_CIDMID[(2, 54)]
        r1 = devices.MODEL_BY_CIDMID[(2, 8)]
        plain_r1 = devices.MODEL_BY_CIDMID[(2, 11)]
        for model in (mad, r1):
            self.assertTrue(model.button_remap)
            self.assertTrue(model.sensor_max)
        self.assertFalse(plain_r1.button_remap)
        self.assertFalse(plain_r1.sensor_max)

    def test_lift_off_choices(self) -> None:
        mad_r = devices.capabilities_for(model=devices.MODEL_BY_CIDMID[(2, 49)], receiver=None)
        self.assertEqual(mad_r.lift_off_choices, [(1, 1.0), (2, 2.0)])
        paw3950 = devices.capabilities_for(model=devices.MODEL_BY_CIDMID[(2, 47)], receiver=None)
        self.assertEqual(paw3950.lift_off_choices, [(3, 0.7), (1, 1.0), (2, 2.0)])

    def test_receiver_ceiling_known(self) -> None:
        for pid, ceiling in ((0x1040, 8000), (0x11A9, 4000), (0xF58E, 1000)):
            self.assertEqual(protocol.RECEIVER_CEILINGS[pid], ceiling)


if __name__ == "__main__":
    unittest.main()
