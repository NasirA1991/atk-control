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

    def test_lift_off_choices(self) -> None:
        mad_r = devices.capabilities_for(model=devices.MODEL_BY_CIDMID[(2, 49)], receiver=None)
        self.assertEqual(mad_r.lift_off_choices, [(1, 1.0), (2, 2.0)])
        self.assertFalse(mad_r.lift_off_scale)
        paw3950 = devices.capabilities_for(model=devices.MODEL_BY_CIDMID[(2, 47)], receiver=None)
        self.assertEqual(paw3950.lift_off_choices, [(3, 0.7), (1, 1.0), (2, 2.0)])

    def test_receiver_ceiling_known(self) -> None:
        for pid, ceiling in ((0x1040, 8000), (0x11A9, 4000), (0xF58E, 1000)):
            self.assertEqual(protocol.RECEIVER_CEILINGS[pid], ceiling)


if __name__ == "__main__":
    unittest.main()
