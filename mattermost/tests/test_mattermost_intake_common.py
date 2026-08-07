from __future__ import annotations

import io
import json
import pathlib
import socket
import tempfile
import threading
import time
import urllib.error
import unittest
from unittest import mock

import os
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import mattermost_intake_common as common


def mmid(seed: str) -> str:
    """Build a deterministic 26-char Mattermost-style id from a short seed."""
    base = "".join(ch for ch in str(seed).lower() if ch.isalnum())
    if not base:
        base = "x"
    return (base * 26)[:26]


TEAM_ID = mmid("team")
OTHER_TEAM_ID = mmid("otherteam")
CHANNEL_ID = mmid("chan")
OTHER_CHANNEL_ID = mmid("chan2")
BOT_USER_ID = mmid("bot")
COMMAND_ID = mmid("cmd")
COMMAND_TOKEN = mmid("tok")
ROOT_POST_ID = mmid("root")
REPLY_POST_ID = mmid("reply")


class MattermostIntakeCommonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        for key in list(os.environ):
            if key.startswith("GC_") or key.startswith("MATTERMOST_"):
                os.environ.pop(key, None)
        os.environ["GC_CITY_ROOT"] = self.tempdir.name
        common._supervisor_scope_cache.clear()
        self.addCleanup(common._supervisor_scope_cache.clear)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    # ------------------------------------------------------------------
    # slash command payloads
    # ------------------------------------------------------------------

    def test_build_command_payload_registers_gc_trigger(self) -> None:
        payload = common.build_command_payload("gc", TEAM_ID, "https://interactions.test/mattermost/command")

        self.assertEqual(payload["trigger"], "gc")
        self.assertEqual(payload["team_id"], TEAM_ID)
        self.assertEqual(payload["method"], "P")
        self.assertEqual(payload["url"], "https://interactions.test/mattermost/command")
        self.assertTrue(payload["auto_complete"])
        self.assertIn("fix", payload["auto_complete_hint"])

    def test_build_command_payload_strips_leading_slash_and_defaults_trigger(self) -> None:
        payload = common.build_command_payload("/gc", TEAM_ID)
        self.assertEqual(payload["trigger"], "gc")

        blank = common.build_command_payload("   ", TEAM_ID)
        self.assertEqual(blank["trigger"], common.COMMAND_NAME_DEFAULT)

    def test_import_app_config_redacts_secret_presence(self) -> None:
        config = common.import_app_config(
            common.load_config(),
            {
                "site_url": "https://mattermost.test/",
                "team_id": TEAM_ID,
                "bot_user_id": BOT_USER_ID,
                "command_id": COMMAND_ID,
                "command_name": "gc",
                "team_allowlist": [TEAM_ID],
            },
        )
        common.save_bot_token("mattermost-bot-token")
        common.save_command_token(COMMAND_TOKEN)

        redacted = common.redact_config(config)

        self.assertEqual(redacted["app"]["site_url"], "https://mattermost.test")
        self.assertEqual(redacted["app"]["team_id"], TEAM_ID)
        self.assertEqual(redacted["app"]["bot_user_id"], BOT_USER_ID)
        self.assertEqual(redacted["app"]["command_id"], COMMAND_ID)
        self.assertTrue(redacted["app"]["bot_token_present"])
        self.assertTrue(redacted["app"]["command_token_present"])
        self.assertEqual(redacted["policy"]["team_allowlist"], [TEAM_ID])

    def test_import_app_config_rejects_invalid_team_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "team_id must be a 26-character Mattermost id"):
            common.import_app_config(common.load_config(), {"team_id": "not-a-mattermost-id"})

    def test_import_app_config_rejects_invalid_site_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "site_url must be an http"):
            common.import_app_config(common.load_config(), {"site_url": "ftp://mattermost.test"})

    def test_shared_mattermost_prompt_requires_bold_speaker_prefix(self) -> None:
        fragment = (
            pathlib.Path(__file__).resolve().parents[1] / "template-fragments" / "mattermost-v0.template.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Always prefix your Mattermost messages with your handle in bold", fragment)
        self.assertIn("**randy:**", fragment)

    # ------------------------------------------------------------------
    # conversation keys (channel_id [+ root_id])
    # ------------------------------------------------------------------

    def test_mattermost_conversation_key_returns_bare_channel_without_root(self) -> None:
        self.assertEqual(common.mattermost_conversation_key(CHANNEL_ID), CHANNEL_ID)
        self.assertEqual(common.mattermost_conversation_key(CHANNEL_ID, ""), CHANNEL_ID)
        self.assertEqual(common.mattermost_conversation_key(f"  {CHANNEL_ID}  ", "  "), CHANNEL_ID)

    def test_mattermost_conversation_key_collapses_root_equal_to_channel(self) -> None:
        self.assertEqual(common.mattermost_conversation_key(CHANNEL_ID, CHANNEL_ID), CHANNEL_ID)

    def test_mattermost_conversation_key_composes_thread_scoped_id(self) -> None:
        self.assertEqual(
            common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID),
            f"{CHANNEL_ID}/{ROOT_POST_ID}",
        )

    def test_mattermost_conversation_parts_splits_thread_scoped_id(self) -> None:
        self.assertEqual(
            common.mattermost_conversation_parts(f"{CHANNEL_ID}/{ROOT_POST_ID}"),
            (CHANNEL_ID, ROOT_POST_ID),
        )

    def test_mattermost_conversation_parts_handles_bare_and_empty_ids(self) -> None:
        self.assertEqual(common.mattermost_conversation_parts(CHANNEL_ID), (CHANNEL_ID, ""))
        self.assertEqual(common.mattermost_conversation_parts(""), ("", ""))
        self.assertEqual(common.mattermost_conversation_parts(f"  {CHANNEL_ID}  "), (CHANNEL_ID, ""))

    def test_mattermost_conversation_parts_round_trips_conversation_key(self) -> None:
        for channel_id, root_id in ((CHANNEL_ID, ""), (CHANNEL_ID, ROOT_POST_ID)):
            key = common.mattermost_conversation_key(channel_id, root_id)
            self.assertEqual(common.mattermost_conversation_parts(key), (channel_id, root_id))

    def test_room_launch_surface_id_prefixes_conversation(self) -> None:
        self.assertEqual(common.room_launch_surface_id(CHANNEL_ID), f"launch-room:{CHANNEL_ID}")

    def test_storage_paths_hash_thread_scoped_ids_instead_of_nesting_directories(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        binding_id = common.chat_binding_id("room", conversation_id)

        cache_path = common.channel_metadata_cache_path(conversation_id)
        budget_path = common.peer_root_budget_path(binding_id, "in-1")

        self.assertEqual(os.path.dirname(cache_path), common.channel_metadata_cache_dir())
        self.assertEqual(os.path.dirname(budget_path), common.peer_root_budget_dir())
        self.assertNotIn("/", os.path.basename(cache_path).removesuffix(".json"))
        self.assertNotIn("/", os.path.basename(budget_path).removesuffix(".json"))

    # ------------------------------------------------------------------
    # channel + rig mappings
    # ------------------------------------------------------------------

    def test_set_channel_mapping_persists_fix_formula(self) -> None:
        config = common.set_channel_mapping(
            common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", "mol-mattermost-fix-issue"
        )

        mapping = common.resolve_channel_mapping(config, TEAM_ID, CHANNEL_ID)

        self.assertIsNotNone(mapping)
        assert mapping is not None
        self.assertEqual(mapping["target"], "product/polecat")
        self.assertEqual(mapping["commands"]["fix"]["formula"], "mol-mattermost-fix-issue")

    def test_set_channel_mapping_rejects_non_polecat_target_for_default_formula(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a rig/polecat sling target"):
            common.set_channel_mapping(
                common.load_config(), TEAM_ID, CHANNEL_ID, "product/witness", common.FIX_FORMULA_DEFAULT
            )

    def test_set_channel_mapping_allows_non_polecat_target_for_custom_formula(self) -> None:
        config = common.set_channel_mapping(
            common.load_config(), TEAM_ID, CHANNEL_ID, "product/witness", "custom-fix-formula"
        )

        mapping = common.resolve_channel_mapping(config, TEAM_ID, CHANNEL_ID)

        assert mapping is not None
        self.assertEqual(mapping["target"], "product/witness")
        self.assertEqual(mapping["commands"]["fix"]["formula"], "custom-fix-formula")

    def test_set_rig_mapping_persists_fix_formula(self) -> None:
        config = common.set_rig_mapping(
            common.load_config(), TEAM_ID, "mission-control", "mission-control/polecat", "mol-mattermost-fix-issue"
        )

        mapping = common.resolve_rig_mapping(config, TEAM_ID, "mission-control")

        assert mapping is not None
        self.assertEqual(mapping["target"], "mission-control/polecat")
        self.assertEqual(mapping["rig_name"], "mission-control")
        self.assertEqual(mapping["commands"]["fix"]["formula"], "mol-mattermost-fix-issue")

    def test_normalize_config_preserves_distinct_mixed_case_rig_entries(self) -> None:
        config = common.normalize_config(
            {
                "rigs": {
                    f"{TEAM_ID}/Mission-Control": {
                        "team_id": TEAM_ID,
                        "rig_name": "Mission-Control",
                        "target": "mission-control/polecat",
                        "commands": {"fix": {"formula": "mol-mattermost-fix-issue"}},
                    },
                    f"{TEAM_ID}/mission-control": {
                        "team_id": TEAM_ID,
                        "rig_name": "mission-control",
                        "target": "product/polecat",
                        "commands": {"fix": {"formula": "mol-mattermost-fix-issue"}},
                    },
                }
            }
        )

        self.assertIn(f"{TEAM_ID}/Mission-Control", config["rigs"])
        self.assertIn(f"{TEAM_ID}/mission-control", config["rigs"])
        self.assertEqual(config["rigs"][f"{TEAM_ID}/Mission-Control"]["target"], "mission-control/polecat")
        self.assertEqual(config["rigs"][f"{TEAM_ID}/mission-control"]["target"], "product/polecat")

    # ------------------------------------------------------------------
    # chat bindings
    # ------------------------------------------------------------------

    def test_set_chat_binding_persists_room_binding(self) -> None:
        config = common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["sky", "lawrence"], TEAM_ID)

        binding = common.resolve_chat_binding(config, f"room:{CHANNEL_ID}")

        assert binding is not None
        self.assertEqual(binding["team_id"], TEAM_ID)
        self.assertEqual(binding["channel_id"], CHANNEL_ID)
        self.assertEqual(binding["root_id"], "")
        self.assertEqual(binding["session_names"], ["sky", "lawrence"])
        self.assertEqual(binding["policy"], common.default_room_peer_policy())

    def test_set_chat_binding_deduplicates_participants_case_insensitively(self) -> None:
        config = common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["sky", "Sky", "lawrence"], TEAM_ID)

        binding = common.resolve_chat_binding(config, f"room:{CHANNEL_ID}")

        assert binding is not None
        self.assertEqual(binding["session_names"], ["sky", "lawrence"])

    def test_set_chat_binding_rejects_dm_fanout(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one session name"):
            common.set_chat_binding(common.load_config(), "dm", CHANNEL_ID, ["sky", "lawrence"])

    def test_set_chat_binding_rejects_unknown_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "kind must be dm or room"):
            common.set_chat_binding(common.load_config(), "thread", CHANNEL_ID, ["sky"])

    def test_set_chat_binding_persists_room_peer_policy(self) -> None:
        config = common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL_ID,
            ["corp--sky", "corp--priya"],
            TEAM_ID,
            policy={
                "ambient_read_enabled": True,
                "peer_fanout_enabled": True,
                "allow_untargeted_peer_fanout": True,
                "max_peer_triggered_publishes_per_root": 2,
                "max_total_peer_deliveries_per_root": 9,
                "max_peer_triggered_publishes_per_session_per_minute": 7,
            },
        )

        binding = common.resolve_chat_binding(config, f"room:{CHANNEL_ID}")

        assert binding is not None
        self.assertTrue(binding["policy"]["ambient_read_enabled"])
        self.assertTrue(binding["policy"]["peer_fanout_enabled"])
        self.assertTrue(binding["policy"]["allow_untargeted_peer_fanout"])
        self.assertEqual(binding["policy"]["max_peer_triggered_publishes_per_root"], 2)
        self.assertEqual(binding["policy"]["max_total_peer_deliveries_per_root"], 9)
        self.assertEqual(binding["policy"]["max_peer_triggered_publishes_per_session_per_minute"], 7)

    def test_set_chat_binding_persists_untargeted_ambient_delivery_policy(self) -> None:
        config = common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL_ID,
            ["randy"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "allow_untargeted_ambient_delivery": True},
        )

        binding = common.resolve_chat_binding(config, f"room:{CHANNEL_ID}")

        assert binding is not None
        self.assertTrue(binding["policy"]["ambient_read_enabled"])
        self.assertTrue(binding["policy"]["allow_untargeted_ambient_delivery"])

    def test_set_chat_binding_rejects_untargeted_ambient_delivery_without_ambient_read(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires ambient read to be enabled"):
            common.set_chat_binding(
                common.load_config(),
                "room",
                CHANNEL_ID,
                ["randy"],
                TEAM_ID,
                policy={"allow_untargeted_ambient_delivery": True},
            )

    def test_set_chat_binding_rejects_untargeted_ambient_delivery_for_multi_session_room(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires exactly one session name"):
            common.set_chat_binding(
                common.load_config(),
                "room",
                CHANNEL_ID,
                ["randy", "wendy"],
                TEAM_ID,
                policy={"ambient_read_enabled": True, "allow_untargeted_ambient_delivery": True},
            )

    def test_set_chat_binding_persists_room_channel_metadata(self) -> None:
        config = common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL_ID,
            ["sky"],
            TEAM_ID,
            channel_metadata={
                "channel_type": "P",
                "channel_team_id": TEAM_ID,
                "channel_name": "eng-private",
                "channel_display_name": "Eng Private",
            },
        )

        binding = common.resolve_chat_binding(config, f"room:{CHANNEL_ID}")

        assert binding is not None
        self.assertEqual(binding["channel_type"], "P")
        self.assertEqual(binding["channel_team_id"], TEAM_ID)
        self.assertEqual(binding["channel_name"], "eng-private")
        self.assertEqual(binding["channel_display_name"], "Eng Private")

    def test_set_chat_binding_merges_existing_room_peer_policy(self) -> None:
        config = common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL_ID,
            ["corp--sky", "corp--priya"],
            TEAM_ID,
            policy={"ambient_read_enabled": True, "peer_fanout_enabled": True, "allow_untargeted_peer_fanout": True},
        )
        config = common.set_chat_binding(
            config,
            "room",
            CHANNEL_ID,
            ["corp--sky", "corp--priya"],
            TEAM_ID,
            policy={"allow_untargeted_peer_fanout": False},
        )

        binding = common.resolve_chat_binding(config, f"room:{CHANNEL_ID}")

        assert binding is not None
        self.assertTrue(binding["policy"]["ambient_read_enabled"])
        self.assertTrue(binding["policy"]["peer_fanout_enabled"])
        self.assertFalse(binding["policy"]["allow_untargeted_peer_fanout"])

    def test_set_chat_binding_rejects_noncanonical_names_when_peer_fanout_enabled(self) -> None:
        with self.assertRaisesRegex(ValueError, "lowercase canonical session names"):
            common.set_chat_binding(
                common.load_config(),
                "room",
                CHANNEL_ID,
                ["Corp--Sky", "corp--priya"],
                TEAM_ID,
                policy={"peer_fanout_enabled": True},
            )

    def test_binding_is_direct_detects_dm_kind_and_direct_channel_types(self) -> None:
        self.assertTrue(common.binding_is_direct({"kind": "dm"}))
        self.assertTrue(common.binding_is_direct({"kind": "room", "channel_type": "D"}))
        self.assertTrue(common.binding_is_direct({"kind": "room", "channel_type": "G"}))
        self.assertFalse(common.binding_is_direct({"kind": "room", "channel_type": "O"}))

    def test_list_chat_bindings_sorts_by_kind_and_conversation(self) -> None:
        config = common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["sky"], TEAM_ID)
        config = common.set_chat_binding(config, "dm", OTHER_CHANNEL_ID, ["priya"], TEAM_ID)

        bindings = common.list_chat_bindings(config)

        self.assertEqual([item["id"] for item in bindings], [f"dm:{OTHER_CHANNEL_ID}", f"room:{CHANNEL_ID}"])

    # ------------------------------------------------------------------
    # thread-scoped bindings (bind-room --root-id)
    # ------------------------------------------------------------------

    def test_set_chat_binding_splits_thread_scoped_conversation_id(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        config = common.set_chat_binding(common.load_config(), "room", conversation_id, ["corp--sky"], TEAM_ID)

        binding = common.resolve_chat_binding(config, f"room:{conversation_id}")

        assert binding is not None
        self.assertEqual(binding["conversation_id"], conversation_id)
        self.assertEqual(binding["channel_id"], CHANNEL_ID)
        self.assertEqual(binding["root_id"], ROOT_POST_ID)

    def test_thread_scoped_binding_survives_save_normalize_load_round_trip(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        common.set_chat_binding(common.load_config(), "room", conversation_id, ["corp--sky"], TEAM_ID)

        # Round trip through disk: load_config() re-normalizes whatever was saved.
        reloaded = common.load_config()
        binding = common.resolve_chat_binding(reloaded, f"room:{conversation_id}")

        assert binding is not None
        self.assertEqual(binding["conversation_id"], conversation_id)
        self.assertEqual(binding["channel_id"], CHANNEL_ID)
        self.assertEqual(binding["root_id"], ROOT_POST_ID)

        # And a second save/load cycle must not drift.
        resaved = common.save_config(reloaded)
        again = common.resolve_chat_binding(common.load_config(), f"room:{conversation_id}")
        assert again is not None
        self.assertEqual(again["channel_id"], CHANNEL_ID)
        self.assertEqual(again["root_id"], ROOT_POST_ID)
        self.assertEqual(resaved["chat"]["bindings"][f"room:{conversation_id}"]["root_id"], ROOT_POST_ID)

    def test_normalize_config_derives_channel_and_root_for_legacy_bindings(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        config = common.normalize_config(
            {
                "chat": {
                    "bindings": {
                        f"room:{conversation_id}": {
                            "id": f"room:{conversation_id}",
                            "kind": "room",
                            "conversation_id": conversation_id,
                            "team_id": TEAM_ID,
                            "session_names": ["corp--sky"],
                        }
                    }
                }
            }
        )

        binding = config["chat"]["bindings"][f"room:{conversation_id}"]
        self.assertEqual(binding["channel_id"], CHANNEL_ID)
        self.assertEqual(binding["root_id"], ROOT_POST_ID)

    def test_normalize_config_preserves_explicit_binding_channel_id(self) -> None:
        config = common.normalize_config(
            {
                "chat": {
                    "bindings": {
                        f"room:{CHANNEL_ID}": {
                            "id": f"room:{CHANNEL_ID}",
                            "kind": "room",
                            "conversation_id": CHANNEL_ID,
                            "channel_id": CHANNEL_ID,
                            "root_id": ROOT_POST_ID,
                            "team_id": TEAM_ID,
                            "session_names": ["corp--sky"],
                        }
                    }
                }
            }
        )

        binding = config["chat"]["bindings"][f"room:{CHANNEL_ID}"]
        self.assertEqual(binding["channel_id"], CHANNEL_ID)
        self.assertEqual(binding["root_id"], ROOT_POST_ID)

    def test_resolve_publish_channel_id_returns_channel_for_thread_scoped_binding(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        common.set_chat_binding(common.load_config(), "room", conversation_id, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{conversation_id}")
        assert binding is not None

        self.assertEqual(common.resolve_publish_channel_id(binding, ""), CHANNEL_ID)
        self.assertEqual(common.resolve_publish_channel_id(binding, CHANNEL_ID), CHANNEL_ID)

    def test_resolve_publish_channel_id_rejects_composite_conversation_override(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        common.set_chat_binding(common.load_config(), "room", conversation_id, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{conversation_id}")
        assert binding is not None

        with self.assertRaisesRegex(ValueError, "must match the bound channel"):
            common.resolve_publish_channel_id(binding, conversation_id)

    def test_resolve_publish_channel_id_rejects_dm_override(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", CHANNEL_ID, ["sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"dm:{CHANNEL_ID}")
        assert binding is not None

        with self.assertRaisesRegex(ValueError, "cannot override a DM binding"):
            common.resolve_publish_channel_id(binding, OTHER_CHANNEL_ID)

    def test_resolve_publish_channel_id_falls_back_to_conversation_parts(self) -> None:
        binding = {
            "id": f"room:{CHANNEL_ID}/{ROOT_POST_ID}",
            "kind": "room",
            "conversation_id": f"{CHANNEL_ID}/{ROOT_POST_ID}",
        }

        self.assertEqual(common.resolve_publish_channel_id(binding, ""), CHANNEL_ID)

    def test_resolve_publish_destination_pins_thread_scoped_binding_root(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        common.set_chat_binding(common.load_config(), "room", conversation_id, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{conversation_id}")
        assert binding is not None

        with mock.patch.object(common, "resolve_thread_root_id") as resolve_thread_root_id:
            channel_id, root_post_id, launch = common.resolve_publish_destination(
                binding,
                reply_to_message_id=REPLY_POST_ID,
            )

        self.assertEqual(channel_id, CHANNEL_ID)
        self.assertEqual(root_post_id, ROOT_POST_ID)
        self.assertIsNone(launch)
        resolve_thread_root_id.assert_not_called()

    def test_publish_binding_message_thread_scoped_binding_posts_to_real_channel(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        common.set_chat_binding(common.load_config(), "room", conversation_id, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{conversation_id}")
        assert binding is not None

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-1"}) as post_channel_message:
            payload = common.publish_binding_message(binding, "hello humans", trigger_id=REPLY_POST_ID)

        post_channel_message.assert_called_once_with(
            CHANNEL_ID,
            "hello humans",
            root_id=ROOT_POST_ID,
            file_ids=None,
        )
        self.assertEqual(payload["record"]["conversation_id"], CHANNEL_ID)
        self.assertEqual(payload["record"]["root_post_id"], ROOT_POST_ID)
        self.assertEqual(payload["record"]["binding_conversation_id"], conversation_id)

    def test_publish_binding_message_thread_scoped_binding_accepts_real_channel_override(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        common.set_chat_binding(common.load_config(), "room", conversation_id, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{conversation_id}")
        assert binding is not None

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-2"}) as post_channel_message:
            common.publish_binding_message(binding, "hi", requested_conversation_id=CHANNEL_ID)

        post_channel_message.assert_called_once_with(CHANNEL_ID, "hi", root_id=ROOT_POST_ID, file_ids=None)

    def test_publish_binding_message_thread_scoped_binding_rejects_composite_override(self) -> None:
        conversation_id = common.mattermost_conversation_key(CHANNEL_ID, ROOT_POST_ID)
        common.set_chat_binding(common.load_config(), "room", conversation_id, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{conversation_id}")
        assert binding is not None

        with mock.patch.object(common, "post_channel_message") as post_channel_message:
            with self.assertRaisesRegex(ValueError, "must match the bound channel"):
                common.publish_binding_message(binding, "hi", requested_conversation_id=conversation_id)

        post_channel_message.assert_not_called()

    def test_publish_binding_message_whole_channel_binding_resolves_root_from_reply_target(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL_ID}")
        assert binding is not None

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-3"}) as post_channel_message, mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": REPLY_POST_ID, "channel_id": CHANNEL_ID, "root_id": ROOT_POST_ID},
        ) as mattermost_api_request:
            common.publish_binding_message(binding, "threaded reply", reply_to_message_id=REPLY_POST_ID)

        mattermost_api_request.assert_called_once()
        post_channel_message.assert_called_once_with(
            CHANNEL_ID,
            "threaded reply",
            root_id=ROOT_POST_ID,
            file_ids=None,
        )

    def test_publish_binding_message_whole_channel_binding_posts_unthreaded_without_reply_target(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL_ID}")
        assert binding is not None

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-4"}) as post_channel_message:
            common.publish_binding_message(binding, "channel note")

        post_channel_message.assert_called_once_with(CHANNEL_ID, "channel note", root_id="", file_ids=None)

    def test_resolve_thread_root_id_walks_reply_to_thread_root(self) -> None:
        with mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": REPLY_POST_ID, "channel_id": CHANNEL_ID, "root_id": ROOT_POST_ID},
        ):
            self.assertEqual(common.resolve_thread_root_id(CHANNEL_ID, REPLY_POST_ID), ROOT_POST_ID)

    def test_resolve_thread_root_id_returns_post_id_for_root_post(self) -> None:
        with mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": ROOT_POST_ID, "channel_id": CHANNEL_ID, "root_id": ""},
        ):
            self.assertEqual(common.resolve_thread_root_id(CHANNEL_ID, ROOT_POST_ID), ROOT_POST_ID)

    def test_resolve_thread_root_id_rejects_cross_channel_post(self) -> None:
        with mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": REPLY_POST_ID, "channel_id": OTHER_CHANNEL_ID, "root_id": ROOT_POST_ID},
        ):
            self.assertEqual(common.resolve_thread_root_id(CHANNEL_ID, REPLY_POST_ID), "")

    def test_resolve_thread_root_id_falls_back_to_post_id_on_api_error(self) -> None:
        with mock.patch.object(
            common,
            "mattermost_api_request",
            side_effect=common.MattermostAPIError("GET failed", status_code=500),
        ):
            self.assertEqual(common.resolve_thread_root_id(CHANNEL_ID, REPLY_POST_ID), REPLY_POST_ID)

    # ------------------------------------------------------------------
    # room launchers
    # ------------------------------------------------------------------

    def test_set_room_launcher_persists_room_launcher(self) -> None:
        config = common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)

        launcher = common.resolve_room_launcher(config, CHANNEL_ID)

        assert launcher is not None
        self.assertEqual(launcher["id"], f"launch-room:{CHANNEL_ID}")
        self.assertEqual(launcher["response_mode"], "mention_only")
        self.assertTrue(launcher["policy"]["peer_fanout_enabled"])
        self.assertTrue(launcher["policy"]["allow_untargeted_peer_fanout"])

    def test_set_room_launcher_can_disable_peer_fanout_policy(self) -> None:
        config = common.set_room_launcher(
            common.load_config(),
            TEAM_ID,
            CHANNEL_ID,
            policy={"peer_fanout_enabled": False, "allow_untargeted_peer_fanout": False},
        )

        launcher = common.resolve_room_launcher(config, CHANNEL_ID)

        assert launcher is not None
        self.assertFalse(launcher["policy"]["peer_fanout_enabled"])
        self.assertFalse(launcher["policy"]["allow_untargeted_peer_fanout"])

    def test_set_chat_binding_rejects_room_with_launcher(self) -> None:
        config = common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)

        with self.assertRaisesRegex(ValueError, "room launch is already enabled"):
            common.set_chat_binding(config, "room", CHANNEL_ID, ["sky"], TEAM_ID)

    def test_set_room_launcher_rejects_direct_binding_conflict(self) -> None:
        config = common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["sky"], TEAM_ID)

        with self.assertRaisesRegex(ValueError, "directly bound room"):
            common.set_room_launcher(config, TEAM_ID, CHANNEL_ID)

    def test_set_room_launcher_rejects_unqualified_default_handle(self) -> None:
        with self.assertRaisesRegex(ValueError, "qualified rig/alias syntax"):
            common.set_room_launcher(
                common.load_config(),
                TEAM_ID,
                CHANNEL_ID,
                response_mode="respond_all",
                default_qualified_handle="sky",
            )

    def test_set_room_launcher_requires_team_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "team_id is required"):
            common.set_room_launcher(common.load_config(), "", CHANNEL_ID)

    def test_resolve_publish_route_returns_launcher_as_room_route(self) -> None:
        config = common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)

        route = common.resolve_publish_route(config, f"launch-room:{CHANNEL_ID}")

        assert route is not None
        self.assertEqual(route["publish_route_kind"], "room_launch")
        self.assertEqual(route["kind"], "room")
        self.assertEqual(route["session_names"], [])

    # ------------------------------------------------------------------
    # channel metadata
    # ------------------------------------------------------------------

    def test_normalize_binding_channel_metadata_reads_channel_objects(self) -> None:
        metadata = common.normalize_binding_channel_metadata(
            {
                "id": CHANNEL_ID,
                "type": "O",
                "team_id": TEAM_ID,
                "name": "town-square",
                "display_name": "Town Square",
            }
        )

        self.assertEqual(
            metadata,
            {
                "channel_type": "O",
                "channel_team_id": TEAM_ID,
                "channel_name": "town-square",
                "channel_display_name": "Town Square",
            },
        )

    def test_normalize_binding_channel_metadata_ignores_binding_team_id(self) -> None:
        metadata = common.normalize_binding_channel_metadata(
            {"kind": "room", "team_id": TEAM_ID, "conversation_id": CHANNEL_ID}
        )

        self.assertEqual(metadata, {})

    def test_describe_room_channel_metadata_normalizes_channel(self) -> None:
        with mock.patch.object(common, "load_bot_token", return_value="bot-token"), mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": CHANNEL_ID, "type": "P", "team_id": TEAM_ID, "name": "eng", "display_name": "Eng"},
        ):
            metadata = common.describe_room_channel_metadata(CHANNEL_ID, bot_token="bot-token")

        self.assertEqual(
            metadata,
            {
                "channel_type": "P",
                "channel_team_id": TEAM_ID,
                "channel_name": "eng",
                "channel_display_name": "Eng",
            },
        )

    def test_describe_room_channel_metadata_returns_empty_without_token(self) -> None:
        with mock.patch.object(common, "load_bot_token", return_value=""), mock.patch.object(
            common, "mattermost_api_request"
        ) as mattermost_api_request:
            self.assertEqual(common.describe_room_channel_metadata(CHANNEL_ID), {})

        mattermost_api_request.assert_not_called()

    def test_save_channel_metadata_cache_round_trips_normalized_metadata(self) -> None:
        metadata = common.save_channel_metadata_cache(
            CHANNEL_ID, {"id": CHANNEL_ID, "type": "O", "team_id": TEAM_ID, "name": "town-square"}
        )

        expected = {"channel_type": "O", "channel_team_id": TEAM_ID, "channel_name": "town-square"}
        self.assertEqual(metadata, expected)
        self.assertEqual(common.load_channel_metadata_cache(CHANNEL_ID), expected)

    def test_load_channel_metadata_cache_ignores_invalid_payload(self) -> None:
        common.ensure_layout()
        pathlib.Path(common.channel_metadata_cache_path(CHANNEL_ID)).write_text("{not valid json", encoding="utf-8")

        self.assertEqual(common.load_channel_metadata_cache(CHANNEL_ID), {})

    # ------------------------------------------------------------------
    # channel context
    # ------------------------------------------------------------------

    def test_load_channel_context_uses_direct_mapping_without_api_lookup(self) -> None:
        config = common.set_channel_mapping(
            common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", "mol-mattermost-fix-issue"
        )

        with mock.patch.object(common, "mattermost_api_request") as mattermost_api_request:
            context = common.load_channel_context(config, TEAM_ID, CHANNEL_ID, ROOT_POST_ID)

        self.assertEqual(context["channel_id"], CHANNEL_ID)
        self.assertEqual(context["root_id"], ROOT_POST_ID)
        self.assertEqual(context["mapping"]["target"], "product/polecat")
        mattermost_api_request.assert_not_called()

    def test_load_channel_context_remaps_to_channel_owning_team(self) -> None:
        config = common.set_channel_mapping(
            common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", "mol-mattermost-fix-issue"
        )

        with mock.patch.object(common, "load_bot_token", return_value="bot-token"), mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": CHANNEL_ID, "team_id": TEAM_ID, "type": "O"},
        ):
            context = common.load_channel_context(config, OTHER_TEAM_ID, CHANNEL_ID)

        self.assertEqual(context["team_id"], TEAM_ID)
        self.assertEqual(context["mapping"]["target"], "product/polecat")

    def test_load_channel_context_surfaces_non_404_lookup_errors(self) -> None:
        config = common.set_channel_mapping(
            common.load_config(), TEAM_ID, CHANNEL_ID, "product/polecat", "mol-mattermost-fix-issue"
        )

        with mock.patch.object(common, "load_bot_token", return_value="bot-token"), mock.patch.object(
            common,
            "mattermost_api_request",
            side_effect=common.MattermostAPIError("GET failed", status_code=500),
        ):
            context = common.load_channel_context(config, OTHER_TEAM_ID, CHANNEL_ID)

        self.assertEqual(context["lookup_error"], "GET failed")

    def test_load_channel_context_tolerates_missing_channel(self) -> None:
        config = common.load_config()

        with mock.patch.object(common, "load_bot_token", return_value="bot-token"), mock.patch.object(
            common,
            "mattermost_api_request",
            side_effect=common.MattermostAPIError("not found", status_code=404),
        ):
            context = common.load_channel_context(config, TEAM_ID, CHANNEL_ID)

        self.assertIsNone(context["mapping"])
        self.assertNotIn("lookup_error", context)

    # ------------------------------------------------------------------
    # slash command sync + tokens
    # ------------------------------------------------------------------

    def test_sync_team_commands_creates_command_and_stores_token(self) -> None:
        config = common.import_app_config(common.load_config(), {"site_url": "https://mattermost.test", "team_id": TEAM_ID})

        with mock.patch.object(common, "list_team_commands", return_value=[]), mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": COMMAND_ID, "token": COMMAND_TOKEN, "trigger": "gc"},
        ) as mattermost_api_request:
            command = common.sync_team_commands(config, TEAM_ID, url="https://interactions.test/mattermost/command")

        self.assertEqual(command["id"], COMMAND_ID)
        self.assertEqual(mattermost_api_request.call_args.args[0], "POST")
        self.assertEqual(mattermost_api_request.call_args.args[1], "/commands")
        payload = mattermost_api_request.call_args.kwargs["payload"]
        self.assertEqual(payload["trigger"], "gc")
        self.assertEqual(payload["team_id"], TEAM_ID)
        self.assertEqual(common.load_command_token(), COMMAND_TOKEN)
        self.assertEqual(common.load_config()["app"]["command_id"], COMMAND_ID)

    def test_sync_team_commands_updates_existing_command(self) -> None:
        config = common.import_app_config(common.load_config(), {"site_url": "https://mattermost.test", "team_id": TEAM_ID})

        with mock.patch.object(
            common, "list_team_commands", return_value=[{"id": COMMAND_ID, "trigger": "gc", "team_id": TEAM_ID}]
        ), mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": COMMAND_ID, "token": COMMAND_TOKEN, "trigger": "gc"},
        ) as mattermost_api_request:
            common.sync_team_commands(config, TEAM_ID, url="https://interactions.test/mattermost/command")

        self.assertEqual(mattermost_api_request.call_args.args[0], "PUT")
        self.assertEqual(mattermost_api_request.call_args.args[1], f"/commands/{COMMAND_ID}")

    def test_sync_team_commands_requires_callback_url(self) -> None:
        config = common.import_app_config(common.load_config(), {"site_url": "https://mattermost.test", "team_id": TEAM_ID})

        with self.assertRaisesRegex(common.MattermostAPIError, "interactions service URL is not published"):
            common.sync_team_commands(config, TEAM_ID)

    def test_verify_command_token_matches_saved_token(self) -> None:
        common.save_command_token(COMMAND_TOKEN)

        self.assertTrue(common.verify_command_token(COMMAND_TOKEN))
        self.assertFalse(common.verify_command_token(mmid("other")))
        self.assertFalse(common.verify_command_token(""))

    def test_verify_command_token_is_false_without_saved_token(self) -> None:
        self.assertFalse(common.verify_command_token(COMMAND_TOKEN))

    def test_regenerate_command_token_persists_new_token(self) -> None:
        new_token = mmid("newtoken")
        with mock.patch.object(common, "mattermost_api_request", return_value={"token": new_token}):
            self.assertEqual(common.regenerate_command_token(COMMAND_ID), new_token)

        self.assertEqual(common.load_command_token(), new_token)

    # ------------------------------------------------------------------
    # dialog state signing
    # ------------------------------------------------------------------

    def test_dialog_state_round_trips_nonce(self) -> None:
        state = common.mint_dialog_state("nonce-1")

        self.assertEqual(common.verify_dialog_state(state), "nonce-1")

    def test_dialog_state_rejects_tampered_signature(self) -> None:
        state = common.mint_dialog_state("nonce-1")
        version, nonce, expires, _signature = state.split(":")

        self.assertEqual(common.verify_dialog_state(f"{version}:{nonce}:{expires}:deadbeef"), "")

    def test_dialog_state_rejects_expired_state(self) -> None:
        state = common.mint_dialog_state("nonce-1", ttl_seconds=1)

        with mock.patch.object(common.time, "time", return_value=time.time() + 3600):
            self.assertEqual(common.verify_dialog_state(state), "")

    def test_mint_dialog_state_rejects_colon_in_nonce(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not contain"):
            common.mint_dialog_state("bad:nonce")

    def test_dialog_route_token_is_stable_and_verifiable(self) -> None:
        token = common.dialog_route_token()

        self.assertEqual(token, common.dialog_route_token())
        self.assertTrue(common.verify_dialog_route_token(token))
        self.assertFalse(common.verify_dialog_route_token("nope"))

    # ------------------------------------------------------------------
    # requests / receipts / workflow links
    # ------------------------------------------------------------------

    def test_save_interaction_receipt_is_unique(self) -> None:
        first = common.save_interaction_receipt("abc", {"response_kind": "accepted", "request_id": "mm-1"})
        second = common.save_interaction_receipt("abc", {"response_kind": "accepted", "request_id": "mm-1"})

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(common.load_interaction_receipt("abc")["request_id"], "mm-1")

    def test_replace_interaction_receipt_overwrites_existing_payload(self) -> None:
        common.save_interaction_receipt("abc", {"response_kind": "dialog", "modal_nonce": "nonce-1"})

        common.replace_interaction_receipt("abc", {"response_kind": "accepted", "request_id": "mm-1"})

        receipt = common.load_interaction_receipt("abc")
        self.assertEqual(receipt["response_kind"], "accepted")
        self.assertEqual(receipt["request_id"], "mm-1")

    def test_load_interaction_receipt_ignores_invalid_json(self) -> None:
        pathlib.Path(common.receipt_path("broken")).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(common.receipt_path("broken")).write_text("{", encoding="utf-8")

        self.assertIsNone(common.load_interaction_receipt("broken"))

    def test_load_request_ignores_invalid_json(self) -> None:
        pathlib.Path(common.request_path("broken")).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(common.request_path("broken")).write_text("{", encoding="utf-8")

        self.assertIsNone(common.load_request("broken"))

    def test_build_request_id_and_workflow_key_use_mattermost_prefixes(self) -> None:
        self.assertTrue(common.build_request_id("interaction-1", "fix").startswith("mm-"))
        self.assertEqual(
            common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix"),
            f"mm:team:{TEAM_ID}:conversation:{CHANNEL_ID}:fix",
        )

    def test_list_recent_requests_skips_invalid_json_files(self) -> None:
        common.save_request({"request_id": "mm-valid"})
        pathlib.Path(common.request_path("mm-bad")).write_text("{", encoding="utf-8")

        requests = common.list_recent_requests(limit=5)

        self.assertEqual([item["request_id"] for item in requests], ["mm-valid"])

    def test_prune_requests_removes_expired_records(self) -> None:
        common.save_request({"request_id": "mm-old"})
        path = common.request_path("mm-old")
        expired = time.time() - common.REQUEST_RETENTION_SECONDS - 10
        os.utime(path, (expired, expired))

        common.prune_requests()

        self.assertEqual(common.list_recent_requests(limit=5), [])

    def test_prune_requests_keeps_records_with_active_workflow_links(self) -> None:
        common.save_request({"request_id": "mm-active"})
        common.save_workflow_link(common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix"), "mm-active")
        path = common.request_path("mm-active")
        expired = time.time() - common.REQUEST_RETENTION_SECONDS - 10
        os.utime(path, (expired, expired))

        common.prune_requests()

        self.assertIsNotNone(common.load_request("mm-active"))

    def test_remove_workflow_link_if_request_only_removes_matching_owner(self) -> None:
        key = common.build_workflow_key(TEAM_ID, CHANNEL_ID, "fix")
        common.save_workflow_link(key, "mm-1")

        self.assertFalse(common.remove_workflow_link_if_request(key, "mm-2"))
        self.assertTrue(common.remove_workflow_link_if_request(key, "mm-1"))
        self.assertIsNone(common.load_workflow_link(key))

    def test_pending_modal_round_trips_through_dialog_state(self) -> None:
        common.save_pending_modal({"nonce": "nonce-9", "command": "fix"})
        state = common.mint_dialog_state("nonce-9")

        payload = common.consume_pending_modal(state)

        assert payload is not None
        self.assertEqual(payload["command"], "fix")
        self.assertIsNone(common.load_pending_modal("nonce-9"))

    # ------------------------------------------------------------------
    # gc api plumbing
    # ------------------------------------------------------------------

    def _no_supervisor(self):
        return mock.patch.object(
            common.urllib.request, "urlopen", side_effect=urllib.error.URLError("no supervisor")
        )

    def test_gc_api_base_url_uses_city_toml_bind_and_port(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text('[api]\nbind = "0.0.0.0"\nport = 9555\n', encoding="utf-8")

        with self._no_supervisor():
            self.assertEqual(common.gc_api_base_url(), "http://127.0.0.1:9555")

    def test_gc_api_base_url_uses_ipv6_loopback_for_unspecified_ipv6_bind(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text('[api]\nbind = "::"\nport = 9555\n', encoding="utf-8")

        with self._no_supervisor():
            self.assertEqual(common.gc_api_base_url(), "http://[::1]:9555")

    def test_gc_api_base_url_honors_env_override(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text('[api]\nbind = "0.0.0.0"\nport = 9555\n', encoding="utf-8")
        os.environ["GC_API_BASE_URL"] = "http://override.test:1234/"

        self.assertEqual(common.gc_api_base_url(), "http://override.test:1234")

    def test_gc_api_base_url_prefers_supervisor_api_when_available(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text(
            '[workspace]\nname = "gc"\n[api]\nbind = "0.0.0.0"\nport = 9555\n',
            encoding="utf-8",
        )
        response = mock.Mock()
        response.__enter__ = mock.Mock(
            return_value=mock.Mock(read=mock.Mock(return_value=b'{"items":[{"name":"gc","running":true}]}'))
        )
        response.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(common.urllib.request, "urlopen", return_value=response) as urlopen:
            self.assertEqual(common.gc_api_base_url(), "http://127.0.0.1:8372")

        self.assertEqual(urlopen.call_count, 1)

    def test_gc_api_base_url_uses_site_workspace_name_when_city_toml_omits_name(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text(
            "[workspace]\nmax_active_sessions = 5\n",
            encoding="utf-8",
        )
        site_dir = pathlib.Path(self.tempdir.name, ".gc")
        site_dir.mkdir()
        (site_dir / "site.toml").write_text('workspace_name = "gc"\n', encoding="utf-8")
        common._supervisor_scope_cache.clear()
        response = mock.Mock()
        response.__enter__ = mock.Mock(
            return_value=mock.Mock(read=mock.Mock(return_value=b'{"items":[{"name":"gc","running":true}]}'))
        )
        response.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(common.urllib.request, "urlopen", return_value=response):
            self.assertEqual(common.gc_api_base_url(), "http://127.0.0.1:8372")

    def test_gc_api_base_url_falls_back_to_city_dir_basename_when_no_declared_name(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text("", encoding="utf-8")
        common._supervisor_scope_cache.clear()
        basename = pathlib.Path(self.tempdir.name).name
        body = ('{"items":[{"name":"%s","running":true}]}' % basename).encode("utf-8")
        response = mock.Mock()
        response.__enter__ = mock.Mock(return_value=mock.Mock(read=mock.Mock(return_value=body)))
        response.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(common.urllib.request, "urlopen", return_value=response):
            self.assertEqual(common.gc_api_base_url(), "http://127.0.0.1:8372")

    def test_gc_api_base_url_falls_back_when_supervisor_city_missing(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text(
            '[workspace]\nname = "gc"\n[api]\nbind = "0.0.0.0"\nport = 9555\n',
            encoding="utf-8",
        )
        response = mock.Mock()
        response.__enter__ = mock.Mock(
            return_value=mock.Mock(read=mock.Mock(return_value=b'{"items":[{"name":"other-city","running":true}]}'))
        )
        response.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(common.urllib.request, "urlopen", return_value=response):
            self.assertEqual(common.gc_api_base_url(), "http://127.0.0.1:9555")

    def test_gc_api_request_routes_through_supervisor_city_scope(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text(
            '[workspace]\nname = "gc"\n[api]\nbind = "0.0.0.0"\nport = 9555\n',
            encoding="utf-8",
        )
        common._supervisor_scope_cache.clear()
        cities = mock.Mock()
        cities.__enter__ = mock.Mock(
            return_value=mock.Mock(read=mock.Mock(return_value=b'{"items":[{"name":"gc","running":true}]}'))
        )
        cities.__exit__ = mock.Mock(return_value=False)
        sessions = mock.Mock()
        sessions.__enter__ = mock.Mock(return_value=mock.Mock(read=mock.Mock(return_value=b'{"items": []}')))
        sessions.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(common.urllib.request, "urlopen", side_effect=[cities, sessions]) as urlopen:
            payload = common.gc_api_request("GET", "/v0/sessions")

        self.assertEqual(payload, {"items": []})
        self.assertEqual(urlopen.call_args_list[-1].args[0].full_url, "http://127.0.0.1:8372/v0/city/gc/sessions")

    def test_gc_api_base_url_rejects_disabled_port(self) -> None:
        pathlib.Path(self.tempdir.name, "city.toml").write_text("[api]\nport = 0\n", encoding="utf-8")

        with self._no_supervisor():
            with self.assertRaisesRegex(common.GCAPIError, "gc api is disabled"):
                common.gc_api_base_url()

    def test_deliver_session_message_uses_messages_endpoint_for_default_intent(self) -> None:
        with mock.patch.object(common, "gc_api_request", return_value={"status": "accepted"}) as gc_api_request:
            payload = common.deliver_session_message("corp--sky", "hello", idempotency_key="ingress:1")

        self.assertEqual(payload, {"status": "accepted"})
        gc_api_request.assert_called_once_with(
            "POST",
            "/v0/session/corp--sky/messages",
            payload={"message": "hello"},
            headers={"Idempotency-Key": "ingress:1"},
            timeout=common.GC_API_REQUEST_TIMEOUT_SECONDS,
        )

    def test_deliver_session_message_uses_submit_endpoint_for_follow_up_intent(self) -> None:
        with mock.patch.object(common, "gc_api_request", return_value={"status": "accepted"}) as gc_api_request:
            payload = common.deliver_session_message(
                "corp--sky",
                "hello again",
                idempotency_key="ingress:2",
                intent="follow_up",
            )

        self.assertEqual(payload, {"status": "accepted"})
        gc_api_request.assert_called_once_with(
            "POST",
            "/v0/session/corp--sky/submit",
            payload={"message": "hello again", "intent": "follow_up"},
            headers={"Idempotency-Key": "ingress:2"},
            timeout=common.GC_API_REQUEST_TIMEOUT_SECONDS,
        )

    # ------------------------------------------------------------------
    # service sockets
    # ------------------------------------------------------------------

    def test_prepare_service_socket_rejects_active_listener(self) -> None:
        socket_path = pathlib.Path(self.tempdir.name, "mattermost.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(1)
        self.addCleanup(listener.close)
        self.addCleanup(lambda: socket_path.exists() and socket_path.unlink())

        with self.assertRaisesRegex(RuntimeError, "refusing to replace active service socket"):
            common.prepare_service_socket(str(socket_path))

    def test_prepare_service_socket_removes_stale_socket_file(self) -> None:
        socket_path = pathlib.Path(self.tempdir.name, "mattermost-stale.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(socket_path))
        listener.listen(1)
        listener.close()
        self.addCleanup(lambda: socket_path.exists() and socket_path.unlink())

        common.prepare_service_socket(str(socket_path))

        self.assertFalse(socket_path.exists())

    # ------------------------------------------------------------------
    # publish + ingress records
    # ------------------------------------------------------------------

    def test_save_chat_publish_lists_recent_records(self) -> None:
        common.save_chat_publish({"publish_id": "pub-1", "binding_id": f"room:{CHANNEL_ID}"})

        recent = common.list_recent_chat_publishes(limit=5)

        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["publish_id"], "pub-1")

    def test_prune_chat_publishes_removes_expired_records(self) -> None:
        common.save_chat_publish({"publish_id": "pub-old", "binding_id": f"room:{CHANNEL_ID}"})
        path = common.chat_publish_path("pub-old")
        expired = time.time() - common.CHAT_PUBLISH_RETENTION_SECONDS - 10
        os.utime(path, (expired, expired))

        common.prune_chat_publishes()

        self.assertEqual(common.list_recent_chat_publishes(limit=5), [])

    def test_save_chat_ingress_if_absent_only_claims_once(self) -> None:
        payload = {"ingress_id": "in-claim", "status": "processing"}
        barrier = threading.Barrier(2)
        results: list[tuple[bool, dict[str, object]]] = []

        def claim() -> None:
            barrier.wait()
            results.append(common.save_chat_ingress_if_absent(payload))

        threads = [threading.Thread(target=claim), threading.Thread(target=claim)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sum(1 for created, _ in results if created), 1)
        self.assertEqual(sum(1 for created, _ in results if not created), 1)

    def test_save_chat_ingress_if_absent_marks_unreadable_claim_conflict(self) -> None:
        path = common.chat_ingress_path("in-broken")
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(path).write_text("", encoding="utf-8")

        created, receipt = common.save_chat_ingress_if_absent({"ingress_id": "in-broken", "status": "processing"})

        self.assertFalse(created)
        self.assertEqual(receipt["status"], "claim_conflict_unreadable")
        self.assertEqual(receipt["reason"], "ingress_claim_unreadable")

    def test_build_status_snapshot_redacts_chat_content(self) -> None:
        common.save_request(
            {
                "request_id": "mm-1",
                "summary": "secret bug",
                "context_markdown": "trace here",
                "invoking_user_display_name": "alice",
                "error_message": "boom",
                "traceback": "stack",
            }
        )
        common.save_gateway_status({"last_message_preview": "peek", "last_error": "boom"})
        common.save_chat_ingress(
            {
                "ingress_id": "in-1",
                "from_display": "alice",
                "from_username": "alice",
                "from_user_id": "u-1",
                "body_preview": "super secret body",
                "status": "delivered",
            }
        )
        common.save_chat_publish({"publish_id": "pub-1", "binding_id": f"room:{CHANNEL_ID}", "body": "internal reply"})

        snapshot = common.build_status_snapshot(limit=5)

        self.assertEqual(snapshot["recent_requests"][0]["summary"], "[redacted]")
        self.assertEqual(snapshot["recent_requests"][0]["context_markdown"], "[redacted]")
        self.assertEqual(snapshot["recent_requests"][0]["invoking_user_display_name"], "[redacted]")
        self.assertEqual(snapshot["recent_requests"][0]["error_message"], "[redacted]")
        self.assertEqual(snapshot["recent_requests"][0]["traceback"], "[redacted]")
        self.assertEqual(snapshot["gateway_status"]["last_message_preview"], "[redacted]")
        self.assertEqual(snapshot["gateway_status"]["last_error"], "[redacted]")
        self.assertEqual(snapshot["recent_chat_ingress"][0]["from_display"], "[redacted]")
        self.assertEqual(snapshot["recent_chat_ingress"][0]["from_username"], "[redacted]")
        self.assertEqual(snapshot["recent_chat_ingress"][0]["from_user_id"], "[redacted]")
        self.assertEqual(snapshot["recent_chat_ingress"][0]["body_preview"], "[redacted]")
        self.assertEqual(snapshot["recent_chat_publishes"][0]["body"], "[redacted]")

    # ------------------------------------------------------------------
    # session identity
    # ------------------------------------------------------------------

    def test_session_index_by_name_prefers_routable_duplicate(self) -> None:
        with mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {"session_name": "corp--sky", "state": "awake", "running": False, "created_at": "2026-03-18T07:55:10Z"},
                {"session_name": "corp--sky", "state": "", "running": False, "created_at": "2026-03-17T05:10:53Z"},
            ],
        ):
            index = common.session_index_by_name()

        self.assertEqual(index["corp--sky"]["state"], "awake")
        self.assertEqual(index["corp--sky"]["created_at"], "2026-03-18T07:55:10Z")

    def test_session_index_by_name_prefers_running_duplicate(self) -> None:
        with mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {"session_name": "corp--sky", "state": "awake", "running": False, "created_at": "2026-03-18T07:55:10Z"},
                {"session_name": "corp--sky", "state": "active", "running": True, "created_at": "2026-03-18T07:55:10Z"},
            ],
        ):
            index = common.session_index_by_name()

        self.assertEqual(index["corp--sky"]["state"], "active")
        self.assertTrue(index["corp--sky"]["running"])

    def test_resolve_session_identity_prefers_routable_named_session(self) -> None:
        with mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {"id": "gc-old", "session_name": "corp--sky", "state": "", "running": False, "created_at": "2026-03-18T00:00:00Z"},
                {"id": "gc-new", "session_name": "corp--sky", "state": "active", "running": True, "created_at": "2026-03-19T00:00:00Z"},
            ],
        ):
            identity = common.resolve_session_identity("corp--sky")

        self.assertEqual(identity["session_name"], "corp--sky")
        self.assertEqual(identity["session_id"], "gc-new")

    def test_current_session_selector_falls_back_to_gc_alias(self) -> None:
        os.environ.pop("GC_SESSION_ID", None)
        os.environ.pop("GC_SESSION_NAME", None)
        os.environ["GC_ALIAS"] = "mm-123-sky"

        self.assertEqual(common.current_session_selector(), "mm-123-sky")

    # ------------------------------------------------------------------
    # reply context discovery
    # ------------------------------------------------------------------

    def test_find_latest_mattermost_reply_context_uses_latest_event(self) -> None:
        with mock.patch.object(
            common,
            "gc_api_request",
            return_value={
                "messages": [
                    {
                        "type": "user",
                        "message": {
                            "content": "<mattermost-event>\npublish_binding_id: dm:1\npublish_trigger_id: older\n</mattermost-event>"
                        },
                    },
                    {
                        "type": "user",
                        "message": {
                            "content": (
                                "<mattermost-event>\n"
                                f"publish_binding_id: room:{CHANNEL_ID}\n"
                                f"publish_conversation_id: {CHANNEL_ID}\n"
                                "publish_trigger_id: newer\n"
                                f"publish_root_post_id: {ROOT_POST_ID}\n"
                                "</mattermost-event>"
                            )
                        },
                    },
                ]
            },
        ) as gc_api_request:
            fields = common.find_latest_mattermost_reply_context("corp--sky", tail=5)

        gc_api_request.assert_called_once()
        self.assertEqual(fields["publish_binding_id"], f"room:{CHANNEL_ID}")
        self.assertEqual(fields["publish_conversation_id"], CHANNEL_ID)
        self.assertEqual(fields["publish_trigger_id"], "newer")
        self.assertEqual(fields["publish_root_post_id"], ROOT_POST_ID)

    def test_find_latest_mattermost_reply_context_falls_back_to_delivered_ingress(self) -> None:
        common.save_chat_ingress(
            {
                "ingress_id": "in-older",
                "binding_id": "room:old",
                "conversation_id": "old",
                "mattermost_post_id": "old-post",
                "created_at": "2026-04-20T22:35:00Z",
                "status": "delivered",
                "targets": [
                    {
                        "session_name": "wendy__wendy",
                        "status": "delivered",
                        "response": {"id": "mc-ayq6xi"},
                    }
                ],
            }
        )
        common.save_chat_ingress(
            {
                "ingress_id": "in-newer",
                "binding_id": f"room:{CHANNEL_ID}",
                "conversation_id": CHANNEL_ID,
                "mattermost_post_id": REPLY_POST_ID,
                "root_post_id": ROOT_POST_ID,
                "team_id": TEAM_ID,
                "created_at": "2026-04-20T22:36:00Z",
                "status": "delivered",
                "targets": [
                    {
                        "session_name": "wendy__wendy",
                        "status": "delivered",
                        "response": {"id": "mc-ayq6xi"},
                    }
                ],
            }
        )

        with mock.patch.object(common, "gc_api_request", return_value={"messages": []}):
            fields = common.find_latest_mattermost_reply_context("mc-ayq6xi", tail=5)

        self.assertEqual(fields["kind"], common.HUMAN_MESSAGE_EVENT_KIND)
        self.assertEqual(fields["ingress_receipt_id"], "in-newer")
        self.assertEqual(fields["publish_binding_id"], f"room:{CHANNEL_ID}")
        self.assertEqual(fields["publish_conversation_id"], CHANNEL_ID)
        self.assertEqual(fields["publish_trigger_id"], REPLY_POST_ID)
        self.assertEqual(fields["publish_root_post_id"], ROOT_POST_ID)

    def test_find_latest_mattermost_reply_context_defaults_root_post_to_trigger(self) -> None:
        common.save_chat_ingress(
            {
                "ingress_id": "in-root",
                "binding_id": f"room:{CHANNEL_ID}",
                "conversation_id": CHANNEL_ID,
                "mattermost_post_id": ROOT_POST_ID,
                "created_at": "2026-04-20T22:36:00Z",
                "status": "delivered",
                "targets": [{"session_name": "corp--sky", "status": "delivered", "response": {"id": "gc-sky"}}],
            }
        )

        with mock.patch.object(common, "gc_api_request", return_value={"messages": []}):
            fields = common.find_latest_mattermost_reply_context("gc-sky", tail=5)

        self.assertEqual(fields["publish_root_post_id"], ROOT_POST_ID)

    # ------------------------------------------------------------------
    # mention parsing
    # ------------------------------------------------------------------

    def test_extract_peer_session_mentions_ignores_urls_and_code(self) -> None:
        mentions = common.extract_peer_session_mentions(
            "\n".join(
                [
                    "Talk to @corp--priya please",
                    "Ignore https://example.test/@corp--eve here",
                    "`@corp--lawrence` stays code",
                    "> @corp--eve is quoted",
                    "@channel should not route",
                ]
            )
        )

        self.assertEqual(mentions, ["corp--priya"])

    def test_extract_peer_session_mentions_ignores_double_backtick_code_spans(self) -> None:
        mentions = common.extract_peer_session_mentions("Talk to ``@corp--priya`` later")

        self.assertEqual(mentions, [])

    def test_extract_peer_session_mentions_ignores_fenced_code_blocks(self) -> None:
        mentions = common.extract_peer_session_mentions("```\n@corp--priya\n```\nnothing here")

        self.assertEqual(mentions, [])

    def test_extract_peer_session_mentions_ignores_reserved_mentions(self) -> None:
        mentions = common.extract_peer_session_mentions("@here @all @channel @corp--priya")

        self.assertEqual(mentions, ["corp--priya"])

    def test_extract_agent_handles_finds_bare_and_qualified_handles(self) -> None:
        handles = common.extract_agent_handles("hello @@sky and @@corp/priya")

        self.assertEqual(handles, ["sky", "corp/priya"])

    def test_extract_agent_handles_is_case_insensitive(self) -> None:
        handles = common.extract_agent_handles("hello @@Sky and @@Corp/Priya")

        self.assertEqual(handles, ["sky", "corp/priya"])

    def test_resolve_at_mentions_skips_reserved_names(self) -> None:
        self.assertEqual(common.resolve_at_mentions("@alice hi @bob @channel @here"), ["alice", "bob"])

    # ------------------------------------------------------------------
    # websocket post normalization
    # ------------------------------------------------------------------

    def test_parse_websocket_post_decodes_json_encoded_post(self) -> None:
        post = {"id": REPLY_POST_ID, "channel_id": CHANNEL_ID, "message": "hi"}

        self.assertEqual(common.parse_websocket_post({"post": json.dumps(post)}), post)
        self.assertEqual(common.parse_websocket_post({"post": post}), post)
        self.assertEqual(common.parse_websocket_post({"post": "{not json"}), {})
        self.assertEqual(common.parse_websocket_post({}), {})

    def test_post_is_from_bot_matches_user_id_or_props(self) -> None:
        self.assertTrue(common.post_is_from_bot({"user_id": BOT_USER_ID}, BOT_USER_ID))
        self.assertTrue(common.post_is_from_bot({"user_id": "u-1", "props": {"from_bot": "true"}}, BOT_USER_ID))
        self.assertFalse(common.post_is_from_bot({"user_id": "u-1"}, BOT_USER_ID))

    def test_post_is_system_detects_system_messages(self) -> None:
        self.assertTrue(common.post_is_system({"type": "system_join_channel"}))
        self.assertFalse(common.post_is_system({"type": ""}))

    def test_post_thread_root_id_falls_back_to_post_id(self) -> None:
        self.assertEqual(common.post_thread_root_id({"id": ROOT_POST_ID, "root_id": ""}), ROOT_POST_ID)
        self.assertEqual(common.post_thread_root_id({"id": REPLY_POST_ID, "root_id": ROOT_POST_ID}), ROOT_POST_ID)

    def test_normalize_to_extmsg_message_marks_thread_and_conversation_key(self) -> None:
        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": REPLY_POST_ID,
                        "channel_id": CHANNEL_ID,
                        "root_id": ROOT_POST_ID,
                        "user_id": "u-1",
                        "message": "hello there",
                    }
                ),
                "channel_type": "O",
                "sender_name": "@alice",
            },
            "broadcast": {"channel_id": CHANNEL_ID},
        }

        message = common.normalize_to_extmsg_message(event, TEAM_ID, BOT_USER_ID)

        self.assertEqual(message["provider_message_id"], REPLY_POST_ID)
        self.assertEqual(message["conversation"]["provider"], "mattermost")
        self.assertEqual(message["conversation"]["scope_id"], TEAM_ID)
        self.assertEqual(message["conversation"]["conversation_id"], CHANNEL_ID)
        self.assertEqual(message["conversation"]["thread_root_id"], ROOT_POST_ID)
        self.assertEqual(message["conversation"]["conversation_key"], f"{CHANNEL_ID}/{ROOT_POST_ID}")
        self.assertEqual(message["conversation"]["kind"], "thread")
        self.assertEqual(message["actor"]["display_name"], "alice")
        self.assertFalse(message["actor"]["is_bot"])
        self.assertEqual(message["text"], "hello there")

    def test_normalize_to_extmsg_message_marks_direct_channels_as_dm(self) -> None:
        event = {
            "data": {
                "post": json.dumps({"id": REPLY_POST_ID, "channel_id": CHANNEL_ID, "user_id": "u-1", "message": "hey"}),
                "channel_type": "D",
                "sender_name": "alice",
            }
        }

        message = common.normalize_to_extmsg_message(event, "", BOT_USER_ID)

        self.assertEqual(message["conversation"]["kind"], "dm")
        self.assertEqual(message["conversation"]["scope_id"], "global")
        self.assertEqual(message["conversation"]["conversation_key"], CHANNEL_ID)

    # ------------------------------------------------------------------
    # posting
    # ------------------------------------------------------------------

    def test_post_channel_message_sets_root_id_for_thread_replies(self) -> None:
        with mock.patch.object(common, "mattermost_api_request", return_value={"id": "post-1"}) as mattermost_api_request:
            response = common.post_channel_message(CHANNEL_ID, "hello", root_id=ROOT_POST_ID)

        self.assertEqual(response["id"], "post-1")
        payload = mattermost_api_request.call_args.kwargs["payload"]
        self.assertEqual(payload["channel_id"], CHANNEL_ID)
        self.assertEqual(payload["message"], "hello")
        self.assertEqual(payload["root_id"], ROOT_POST_ID)

    def test_post_channel_message_omits_empty_root_id(self) -> None:
        with mock.patch.object(common, "mattermost_api_request", return_value={"id": "post-1"}) as mattermost_api_request:
            common.post_channel_message(CHANNEL_ID, "hello")

        self.assertNotIn("root_id", mattermost_api_request.call_args.kwargs["payload"])

    def test_post_channel_message_caps_attachments_at_five(self) -> None:
        with mock.patch.object(common, "mattermost_api_request", return_value={"id": "post-1"}) as mattermost_api_request:
            common.post_channel_message(CHANNEL_ID, "files", file_ids=[f"f{index}" for index in range(8)])

        self.assertEqual(len(mattermost_api_request.call_args.kwargs["payload"]["file_ids"]), 5)

    def test_mattermost_permalink_and_channel_url_require_site_url(self) -> None:
        self.assertEqual(common.mattermost_permalink("eng", REPLY_POST_ID), "")

        os.environ["GC_MATTERMOST_URL"] = "https://mattermost.test/"

        self.assertEqual(
            common.mattermost_permalink("eng", REPLY_POST_ID),
            f"https://mattermost.test/eng/pl/{REPLY_POST_ID}",
        )
        self.assertEqual(
            common.mattermost_channel_url("eng", "town-square"),
            "https://mattermost.test/eng/channels/town-square",
        )
        self.assertEqual(common.mattermost_permalink("", REPLY_POST_ID), "")

    # ------------------------------------------------------------------
    # publish_binding_message
    # ------------------------------------------------------------------

    def test_publish_binding_message_requires_remote_post_id(self) -> None:
        common.set_chat_binding(common.load_config(), "dm", CHANNEL_ID, ["sky"])
        binding = common.resolve_chat_binding(common.load_config(), f"dm:{CHANNEL_ID}")
        assert binding is not None

        with mock.patch.object(common, "post_channel_message", return_value={}):
            with self.assertRaisesRegex(common.MattermostAPIError, "returned no post id"):
                common.publish_binding_message(binding, "hello humans", trigger_id=ROOT_POST_ID)

    def test_publish_binding_message_room_launch_activates_thread_on_first_publish(self) -> None:
        config = common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)
        route = common.resolve_publish_route(config, f"launch-room:{CHANNEL_ID}")
        assert route is not None
        common.save_room_launch(
            {
                "launch_id": f"room-launch:{ROOT_POST_ID}",
                "launcher_id": f"launch-room:{CHANNEL_ID}",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
            }
        )

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-1"}) as post_channel_message:
            payload = common.publish_binding_message(
                route,
                "hello humans",
                trigger_id=ROOT_POST_ID,
                source_context={
                    "kind": common.HUMAN_MESSAGE_EVENT_KIND,
                    "publish_launch_id": f"room-launch:{ROOT_POST_ID}",
                },
            )

        post_channel_message.assert_called_once_with(
            CHANNEL_ID,
            "hello humans",
            root_id=ROOT_POST_ID,
            file_ids=None,
        )
        self.assertEqual(payload["record"]["conversation_id"], CHANNEL_ID)
        self.assertEqual(payload["record"]["root_post_id"], ROOT_POST_ID)
        self.assertEqual(payload["record"]["launch_id"], f"room-launch:{ROOT_POST_ID}")
        launch = common.load_room_launch(f"room-launch:{ROOT_POST_ID}")
        assert launch is not None
        self.assertEqual(launch["state"], "active")

    def test_publish_binding_message_records_room_launch_message_target(self) -> None:
        config = common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)
        route = common.resolve_publish_route(config, f"launch-room:{CHANNEL_ID}")
        assert route is not None
        common.save_room_launch(
            {
                "launch_id": "room-launch:target",
                "launcher_id": f"launch-room:{CHANNEL_ID}",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
                "session_name": "mm-sky",
                "state": "active",
                "participants": {
                    "corp/sky": {
                        "qualified_handle": "corp/sky",
                        "session_alias": "mm-123-sky",
                        "session_name": "mm-sky",
                        "session_id": "gc-sky",
                    }
                },
            }
        )

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-launch"}):
            payload = common.publish_binding_message(
                route,
                "hello humans",
                source_context={
                    "kind": common.HUMAN_MESSAGE_EVENT_KIND,
                    "publish_launch_id": "room-launch:target",
                },
                source_session_name="mm-sky",
                source_session_id="gc-sky",
            )

        self.assertEqual(payload["record"]["remote_message_id"], "post-launch")
        self.assertEqual(payload["record"]["source_qualified_handle"], "corp/sky")
        launch = common.load_room_launch("room-launch:target")
        assert launch is not None
        self.assertEqual(launch["message_targets"]["post-launch"], "corp/sky")

    def test_publish_binding_message_room_launch_rejects_foreign_conversation_override(self) -> None:
        config = common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)
        route = common.resolve_publish_route(config, f"launch-room:{CHANNEL_ID}")
        assert route is not None
        common.save_room_launch(
            {
                "launch_id": "room-launch:foreign",
                "launcher_id": f"launch-room:{CHANNEL_ID}",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "state": "active",
            }
        )

        with mock.patch.object(common, "post_channel_message") as post_channel_message:
            with self.assertRaisesRegex(ValueError, "must match the launch channel"):
                common.publish_binding_message(
                    route,
                    "hello",
                    requested_conversation_id=OTHER_CHANNEL_ID,
                    source_context={"kind": common.HUMAN_MESSAGE_EVENT_KIND, "publish_launch_id": "room-launch:foreign"},
                )

        post_channel_message.assert_not_called()

    def test_publish_binding_message_does_not_record_target_for_non_launch_binding(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL_ID}")
        assert binding is not None
        common.save_room_launch(
            {
                "launch_id": "room-launch:untouched",
                "launcher_id": f"launch-room:{CHANNEL_ID}",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
                "session_name": "mm-sky",
                "state": "active",
                "participants": {
                    "corp/sky": {
                        "qualified_handle": "corp/sky",
                        "session_alias": "mm-123-sky",
                        "session_name": "mm-sky",
                        "session_id": "gc-sky",
                    }
                },
            }
        )

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-root"}):
            common.publish_binding_message(
                binding,
                "root-room note",
                source_context={"kind": common.HUMAN_MESSAGE_EVENT_KIND, "publish_launch_id": "room-launch:untouched"},
                source_session_name="mm-sky",
                source_session_id="gc-sky",
            )

        launch = common.load_room_launch("room-launch:untouched")
        assert launch is not None
        self.assertEqual(launch["message_targets"], {ROOT_POST_ID: "corp/sky"})

    def test_publish_binding_message_does_not_fan_out_to_peers(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL_ID,
            ["corp--sky", "corp--priya"],
            TEAM_ID,
            policy={"peer_fanout_enabled": True},
        )
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL_ID}")
        assert binding is not None
        os.environ["GC_SESSION_NAME"] = "corp--sky"
        os.environ["GC_SESSION_ID"] = "gc-sky"

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-1"}), mock.patch.object(
            common, "deliver_session_message"
        ) as deliver_session_message:
            payload = common.publish_binding_message(
                binding,
                "@corp--priya hello",
                trigger_id=ROOT_POST_ID,
                source_context={
                    "kind": common.HUMAN_MESSAGE_EVENT_KIND,
                    "ingress_receipt_id": "in-9",
                    "publish_binding_id": f"room:{CHANNEL_ID}",
                    "publish_conversation_id": CHANNEL_ID,
                    "publish_trigger_id": ROOT_POST_ID,
                    "publish_root_post_id": ROOT_POST_ID,
                },
            )

        record = payload["record"]
        self.assertEqual(record["source_event_kind"], common.HUMAN_MESSAGE_EVENT_KIND)
        self.assertEqual(record["root_ingress_receipt_id"], "in-9")
        self.assertEqual(record["source_session_name"], "corp--sky")
        self.assertEqual(record["source_session_id"], "gc-sky")
        self.assertNotIn("peer_delivery", record)
        deliver_session_message.assert_not_called()

    def test_publish_binding_message_uses_source_root_post_hint(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["corp--sky"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL_ID}")
        assert binding is not None

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-1"}) as post_channel_message, mock.patch.object(
            common,
            "mattermost_api_request",
            return_value={"id": ROOT_POST_ID, "channel_id": CHANNEL_ID, "root_id": ""},
        ):
            common.publish_binding_message(
                binding,
                "hello",
                source_context={
                    "kind": common.HUMAN_MESSAGE_EVENT_KIND,
                    "publish_root_post_id": ROOT_POST_ID,
                },
            )

        post_channel_message.assert_called_once_with(CHANNEL_ID, "hello", root_id=ROOT_POST_ID, file_ids=None)

    def test_publish_binding_message_resolves_source_name_from_id_only_env(self) -> None:
        common.set_chat_binding(common.load_config(), "room", CHANNEL_ID, ["corp--sky", "corp--priya"], TEAM_ID)
        binding = common.resolve_chat_binding(common.load_config(), f"room:{CHANNEL_ID}")
        assert binding is not None
        os.environ.pop("GC_SESSION_NAME", None)
        os.environ["GC_SESSION_ID"] = "gc-sky"

        with mock.patch.object(common, "post_channel_message", return_value={"id": "post-1"}), mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {"id": "gc-sky", "session_name": "corp--sky", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
                {"id": "gc-priya", "session_name": "corp--priya", "state": "active", "running": True, "created_at": "2026-03-21T00:00:00Z"},
            ],
        ):
            payload = common.publish_binding_message(binding, "hello", trigger_id=ROOT_POST_ID)

        self.assertEqual(payload["record"]["source_session_name"], "corp--sky")
        self.assertEqual(payload["record"]["source_session_id"], "gc-sky")

    # ------------------------------------------------------------------
    # room launch records
    # ------------------------------------------------------------------

    def test_normalize_room_launch_record_seeds_root_message_target(self) -> None:
        launch = common.save_room_launch(
            {
                "launch_id": "room-launch:seed",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
            }
        )

        self.assertEqual(launch["message_targets"], {ROOT_POST_ID: "corp/sky"})
        self.assertEqual(launch["message_target_order"], [ROOT_POST_ID])
        self.assertEqual(launch["last_addressed_qualified_handle"], "corp/sky")
        self.assertEqual(common.room_launch_message_target_handle(launch, ROOT_POST_ID), "corp/sky")

    def test_ensure_room_launch_thread_promotes_state_once(self) -> None:
        config = common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)
        binding = common.resolve_publish_route(config, f"launch-room:{CHANNEL_ID}")
        assert binding is not None
        common.save_room_launch(
            {
                "launch_id": "room-launch:promote",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
            }
        )

        current, promoted = common.ensure_room_launch_thread(binding, "room-launch:promote")
        self.assertTrue(promoted)
        self.assertEqual(current["state"], "active")

        current, promoted = common.ensure_room_launch_thread(binding, "room-launch:promote")
        self.assertFalse(promoted)

    def test_ensure_room_launch_thread_requires_routing_metadata(self) -> None:
        config = common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)
        binding = common.resolve_publish_route(config, f"launch-room:{CHANNEL_ID}")
        assert binding is not None
        common.save_room_launch(
            {
                "launch_id": "room-launch:incomplete",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "qualified_handle": "corp/sky",
            }
        )

        with self.assertRaisesRegex(ValueError, "missing thread routing metadata"):
            common.ensure_room_launch_thread(binding, "room-launch:incomplete")

    def test_touch_room_launch_sets_last_activity_at(self) -> None:
        common.save_room_launch(
            {
                "launch_id": "room-launch:activity",
                "launcher_id": f"launch-room:{CHANNEL_ID}",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
            }
        )

        touched = common.touch_room_launch("room-launch:activity")

        assert touched is not None
        self.assertTrue(str(touched.get("last_activity_at", "")).strip())

    def test_set_room_launch_last_addressed_requires_known_participant(self) -> None:
        common.save_room_launch(
            {
                "launch_id": "room-launch:cursor",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "participants": {
                    "corp/sky": {"qualified_handle": "corp/sky", "session_name": "mm-sky"},
                    "corp/priya": {"qualified_handle": "corp/priya", "session_name": "mm-priya"},
                },
            }
        )

        updated = common.set_room_launch_last_addressed("room-launch:cursor", "corp/priya")
        assert updated is not None
        self.assertEqual(updated["last_addressed_qualified_handle"], "corp/priya")

        unchanged = common.set_room_launch_last_addressed("room-launch:cursor", "corp/nobody")
        assert unchanged is not None
        self.assertEqual(unchanged["last_addressed_qualified_handle"], "corp/priya")

    def test_prune_room_launches_keeps_recent_thread_routes(self) -> None:
        common.save_room_launch(
            {
                "launch_id": "room-launch:recent",
                "launcher_id": f"launch-room:{CHANNEL_ID}",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
            }
        )
        path = common.room_launch_path("room-launch:recent")
        aged_but_recent = time.time() - common.CHAT_INGRESS_RETENTION_SECONDS - 10
        os.utime(path, (aged_but_recent, aged_but_recent))

        common.prune_room_launches()

        self.assertIsNotNone(common.load_room_launch("room-launch:recent"))

    def test_room_launch_session_alias_is_deterministic_and_prefixed(self) -> None:
        alias = common.room_launch_session_alias(TEAM_ID, CHANNEL_ID, ROOT_POST_ID, "corp/sky")

        self.assertTrue(alias.startswith("mm-"))
        self.assertTrue(alias.endswith("corp-sky"))
        self.assertEqual(alias, common.room_launch_session_alias(TEAM_ID, CHANNEL_ID, ROOT_POST_ID, "Corp/Sky"))

    # ------------------------------------------------------------------
    # room launch sessions
    # ------------------------------------------------------------------

    def test_ensure_room_launch_session_recreates_non_routable_alias_match(self) -> None:
        launch = {
            "launch_id": "room-launch:revive",
            "qualified_handle": "corp/sky",
            "session_alias": "mm-123-sky",
            "from_display": "alice",
        }

        with mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {
                    "id": "gc-old",
                    "alias": "mm-123-sky",
                    "session_name": "mm-old-sky",
                    "state": "closed",
                    "running": False,
                    "created_at": "2026-03-20T00:00:00Z",
                }
            ],
        ), mock.patch.object(
            common,
            "create_agent_session",
            return_value={"id": "gc-new", "session_name": "mm-new-sky", "alias": "mm-123-sky"},
        ) as create_agent_session, mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-new"},
        ):
            current = common.ensure_room_launch_session(launch)

        create_agent_session.assert_called_once()
        self.assertEqual(current["session_id"], "gc-new")
        self.assertEqual(current["session_name"], "mm-new-sky")

    def test_ensure_room_launch_session_hydrates_routable_identity_after_create(self) -> None:
        launch = {
            "launch_id": "room-launch:hydrate",
            "qualified_handle": "corp/sky",
            "session_alias": "mm-123-sky",
            "from_display": "alice",
        }

        sessions_first: list[dict[str, object]] = [
            {
                "id": "gc-old",
                "alias": "mm-123-sky",
                "session_name": "mm-old-sky",
                "state": "closed",
                "running": False,
                "created_at": "2026-03-20T00:00:00Z",
            }
        ]
        sessions_second: list[dict[str, object]] = [
            {
                "id": "gc-new",
                "alias": "mm-123-sky",
                "session_name": "mm-new-sky",
                "state": "active",
                "running": True,
                "created_at": "2026-03-22T00:00:00Z",
            }
        ]
        calls = {"count": 0}

        def list_sessions(*, state: str = "all") -> list[dict[str, object]]:
            self.assertEqual(state, "all")
            calls["count"] += 1
            if calls["count"] < 4:
                return sessions_first
            return sessions_second

        with mock.patch.object(common, "list_city_sessions", side_effect=list_sessions), mock.patch.object(
            common,
            "create_agent_session",
            return_value={"alias": "mm-123-sky"},
        ) as create_agent_session, mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-new"},
        ), mock.patch.object(common.time, "sleep"):
            current = common.ensure_room_launch_session(launch)

        create_agent_session.assert_called_once()
        self.assertEqual(current["session_id"], "gc-new")
        self.assertEqual(current["session_name"], "mm-new-sky")

    def test_ensure_room_launch_session_hydrates_routable_identity_after_longer_async_delay(self) -> None:
        launch = {
            "launch_id": "room-launch:slow-hydrate",
            "qualified_handle": "corp/maya",
            "session_alias": "mm-123-maya",
            "from_display": "alice",
        }

        calls = {"count": 0}

        def list_sessions(*, state: str = "all") -> list[dict[str, object]]:
            self.assertEqual(state, "all")
            calls["count"] += 1
            if calls["count"] < 25:
                return []
            return [
                {
                    "id": "gc-maya",
                    "alias": "mm-123-maya",
                    "session_name": "s-gc-maya",
                    "state": "active",
                    "running": True,
                    "created_at": "2026-03-23T00:00:00Z",
                }
            ]

        with mock.patch.object(common, "list_city_sessions", side_effect=list_sessions), mock.patch.object(
            common,
            "create_agent_session",
            return_value={"alias": "mm-123-maya"},
        ) as create_agent_session, mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-maya"},
        ), mock.patch.object(common.time, "sleep"):
            current = common.ensure_room_launch_session(launch)

        create_agent_session.assert_called_once()
        self.assertGreaterEqual(calls["count"], 25)
        self.assertEqual(current["session_id"], "gc-maya")
        self.assertEqual(current["session_name"], "s-gc-maya")

    def test_ensure_room_launch_session_primes_new_session_before_first_human_turn(self) -> None:
        launch = {
            "launch_id": "room-launch:prime",
            "qualified_handle": "corp/sky",
            "session_alias": "mm-123-sky",
            "from_display": "alice",
        }

        with mock.patch.object(common, "list_city_sessions", return_value=[]), mock.patch.object(
            common,
            "create_agent_session",
            return_value={"id": "gc-new", "session_name": "mm-new-sky", "alias": "mm-123-sky"},
        ), mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-new"},
        ) as deliver_session_message:
            current = common.ensure_room_launch_session(launch)

        deliver_session_message.assert_called_once()
        self.assertEqual(deliver_session_message.call_args.args[0], "mm-new-sky")
        primer_message = deliver_session_message.call_args.args[1]
        self.assertIn("<mattermost-launch-primer>", primer_message)
        self.assertIn("gc mattermost reply-current --body-file <path>", primer_message)
        self.assertEqual(
            deliver_session_message.call_args.kwargs["idempotency_key"],
            "room-launch:prime:primer:corp/sky:v1",
        )
        participant = current["participants"]["corp/sky"]
        self.assertEqual(participant["primer_version"], common.ROOM_LAUNCH_PRIMER_VERSION)
        self.assertTrue(str(participant.get("primed_at", "")).strip())

    def test_ensure_room_launch_session_raises_when_created_identity_never_becomes_routable(self) -> None:
        launch = {
            "launch_id": "room-launch:stuck",
            "qualified_handle": "corp/sky",
            "session_alias": "mm-123-sky",
            "from_display": "alice",
        }

        with mock.patch.object(common, "list_city_sessions", return_value=[]), mock.patch.object(
            common,
            "create_agent_session",
            return_value={"alias": "mm-123-sky"},
        ), mock.patch.object(common.time, "sleep"), mock.patch.object(
            common, "ROOM_LAUNCH_IDENTITY_RESOLVE_TIMEOUT_SECONDS", 0.01
        ):
            with self.assertRaisesRegex(common.GCAPIError, "created launch session is not routable yet"):
                common.ensure_room_launch_session(launch)

    def test_ensure_room_launch_session_for_handle_creates_secondary_participant(self) -> None:
        common.save_room_launch(
            {
                "launch_id": "room-launch:thread-join",
                "launcher_id": f"launch-room:{CHANNEL_ID}",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-123-sky",
                "session_name": "mm-sky",
            }
        )

        with mock.patch.object(common, "list_city_sessions", return_value=[]), mock.patch.object(
            common,
            "create_agent_session",
            return_value={"id": "gc-alex", "session_name": "mm-alex", "alias": "mm-456-alex"},
        ) as create_agent_session, mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-alex"},
        ):
            current, participant = common.ensure_room_launch_session_for_handle(
                common.load_room_launch("room-launch:thread-join") or {},
                "corp/alex",
            )

        create_agent_session.assert_called_once()
        self.assertEqual(participant["session_name"], "mm-alex")
        self.assertEqual(current["participants"]["corp/alex"]["session_alias"], "mm-456-alex")
        self.assertEqual(current["qualified_handle"], "corp/sky")

    def test_ensure_room_launch_session_for_handle_does_not_reprime_current_participant(self) -> None:
        common.save_room_launch(
            {
                "launch_id": "room-launch:no-reprime",
                "launcher_id": f"launch-room:{CHANNEL_ID}",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "participants": {
                    "corp/sky": {
                        "qualified_handle": "corp/sky",
                        "session_alias": "mm-123-sky",
                        "session_name": "mm-sky",
                        "session_id": "gc-sky",
                        "primer_version": common.ROOM_LAUNCH_PRIMER_VERSION,
                        "primer_identity": "gc-sky",
                        "primed_at": "2026-03-22T00:00:00Z",
                    }
                },
                "session_alias": "mm-123-sky",
                "session_name": "mm-sky",
                "session_id": "gc-sky",
            }
        )

        with mock.patch.object(
            common,
            "list_city_sessions",
            return_value=[
                {
                    "id": "gc-sky",
                    "alias": "mm-123-sky",
                    "session_name": "mm-sky",
                    "state": "active",
                    "running": True,
                    "created_at": "2026-03-22T00:00:00Z",
                }
            ],
        ), mock.patch.object(common, "deliver_session_message") as deliver_session_message:
            current, participant = common.ensure_room_launch_session_for_handle(
                common.load_room_launch("room-launch:no-reprime") or {},
                "corp/sky",
            )

        deliver_session_message.assert_not_called()
        self.assertEqual(participant["primer_version"], common.ROOM_LAUNCH_PRIMER_VERSION)
        self.assertEqual(current["participants"]["corp/sky"]["primed_at"], "2026-03-22T00:00:00Z")

    def test_room_launch_primer_message_mentions_peer_fanout_only_when_enabled(self) -> None:
        launch = {"launch_id": "room-launch:primer", "qualified_handle": "corp/sky", "conversation_id": CHANNEL_ID}
        participant = {"qualified_handle": "corp/sky", "session_name": "mm-sky"}

        enabled = common.room_launch_primer_message(launch, participant, peer_fanout_enabled=True)
        disabled = common.room_launch_primer_message(launch, participant, peer_fanout_enabled=False)

        self.assertIn("@@rig/alias", enabled)
        self.assertNotIn("@@rig/alias", disabled)
        self.assertIn("root_id set to the launch root post id", disabled)

    # ------------------------------------------------------------------
    # peer budgets + retry
    # ------------------------------------------------------------------

    def test_peer_root_budget_index_tracks_root_counts(self) -> None:
        now = common.utcnow()
        common.save_chat_publish(
            {
                "publish_id": "mattermost-publish-1",
                "binding_id": f"room:{CHANNEL_ID}",
                "root_ingress_receipt_id": "in-1",
                "source_session_name": "corp--sky",
                "source_event_kind": common.PEER_PUBLICATION_EVENT_KIND,
                "created_at": now,
                "peer_delivery": {"frozen_targets": ["corp--priya", "corp--eve"]},
            }
        )
        common.save_chat_publish(
            {
                "publish_id": "mattermost-publish-2",
                "binding_id": f"room:{CHANNEL_ID}",
                "root_ingress_receipt_id": "in-1",
                "source_session_name": "corp--sky",
                "source_event_kind": common.PEER_PUBLICATION_EVENT_KIND,
                "created_at": now,
                "peer_delivery": {"frozen_targets": ["corp--lawrence"]},
            }
        )

        self.assertEqual(common._count_root_peer_triggered_publishes(f"room:{CHANNEL_ID}", "in-1", "corp--sky"), 2)
        self.assertEqual(common._count_root_peer_deliveries_from_index(f"room:{CHANNEL_ID}", "in-1"), 3)

    def test_retry_peer_fanout_redrives_failed_target_without_reposting(self) -> None:
        common.set_chat_binding(
            common.load_config(),
            "room",
            CHANNEL_ID,
            ["corp--sky", "corp--priya"],
            TEAM_ID,
            policy={"peer_fanout_enabled": True},
        )
        common.save_chat_publish(
            {
                "publish_id": "mattermost-publish-1",
                "binding_id": f"room:{CHANNEL_ID}",
                "binding_kind": "room",
                "binding_conversation_id": CHANNEL_ID,
                "conversation_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "source_session_name": "corp--sky",
                "source_session_id": "gc-sky",
                "source_event_kind": common.HUMAN_MESSAGE_EVENT_KIND,
                "root_ingress_receipt_id": "in-9",
                "body": "@corp--priya hello",
                "remote_message_id": "post-1",
                "root_post_id": ROOT_POST_ID,
                "peer_delivery": {
                    "phase": "peer_fanout_partial_failure",
                    "status": "partial_failure",
                    "delivery": "targeted",
                    "mentioned_session_names": ["corp--priya"],
                    "frozen_targets": ["corp--priya"],
                    "targets": [
                        {
                            "session_name": "corp--priya",
                            "status": "failed_retryable",
                            "attempt_count": 1,
                            "idempotency_key": f"peer_publish:mattermost-publish-1:binding:room:{CHANNEL_ID}:target:corp--priya",
                            "attempts": [],
                        }
                    ],
                    "budget_snapshot": {},
                },
            }
        )

        with mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-priya"},
        ) as deliver_session_message, mock.patch.object(common, "post_channel_message") as post_channel_message:
            record = common.retry_peer_fanout("mattermost-publish-1")

        self.assertEqual(record["peer_delivery"]["status"], "delivered")
        post_channel_message.assert_not_called()
        deliver_session_message.assert_called_once()
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn(f"channel_id: {CHANNEL_ID}", envelope)
        self.assertIn(f"root_id: {ROOT_POST_ID}", envelope)
        self.assertIn(f"conversation_key: {CHANNEL_ID}/{ROOT_POST_ID}", envelope)

    def test_retry_peer_fanout_room_launch_preserves_launch_context(self) -> None:
        common.set_room_launcher(common.load_config(), TEAM_ID, CHANNEL_ID)
        common.save_room_launch(
            {
                "launch_id": "room-launch:retry",
                "team_id": TEAM_ID,
                "conversation_id": CHANNEL_ID,
                "root_post_id": ROOT_POST_ID,
                "qualified_handle": "corp/sky",
                "session_alias": "mm-thread-corp-sky",
                "session_id": "gc-sky",
                "session_name": "",
                "participants": {
                    "corp/sky": {
                        "qualified_handle": "corp/sky",
                        "session_alias": "mm-thread-corp-sky",
                        "session_id": "gc-sky",
                        "session_name": "",
                    },
                    "corp/priya": {
                        "qualified_handle": "corp/priya",
                        "session_alias": "mm-thread-corp-priya",
                        "session_id": "gc-priya",
                        "session_name": "s-gc-priya",
                    },
                },
                "state": "active",
            }
        )
        common.save_chat_publish(
            {
                "publish_id": "mattermost-publish-launch",
                "binding_id": f"launch-room:{CHANNEL_ID}",
                "binding_kind": "room",
                "binding_conversation_id": CHANNEL_ID,
                "conversation_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "source_session_name": "",
                "source_session_id": "gc-sky",
                "source_event_kind": common.HUMAN_MESSAGE_EVENT_KIND,
                "root_ingress_receipt_id": "in-77",
                "launch_id": "room-launch:retry",
                "body": "@@corp/priya hello",
                "remote_message_id": "post-77",
                "root_post_id": ROOT_POST_ID,
                "peer_delivery": {
                    "phase": "peer_fanout_partial_failure",
                    "status": "partial_failure",
                    "delivery": "targeted",
                    "mentioned_session_names": ["s-gc-priya"],
                    "frozen_targets": ["s-gc-priya"],
                    "targets": [
                        {
                            "session_name": "s-gc-priya",
                            "status": "failed_retryable",
                            "attempt_count": 1,
                            "idempotency_key": f"peer_publish:mattermost-publish-launch:binding:launch-room:{CHANNEL_ID}:target:s-gc-priya",
                            "attempts": [],
                        }
                    ],
                    "budget_snapshot": {},
                },
            }
        )

        with mock.patch.object(common, "list_city_sessions", return_value=[]), mock.patch.object(
            common,
            "deliver_session_message",
            return_value={"status": "accepted", "id": "gc-priya"},
        ) as deliver_session_message, mock.patch.object(common, "post_channel_message") as post_channel_message:
            record = common.retry_peer_fanout("mattermost-publish-launch")

        self.assertEqual(record["peer_delivery"]["status"], "delivered")
        post_channel_message.assert_not_called()
        deliver_session_message.assert_called_once()
        envelope = deliver_session_message.call_args.args[1]
        self.assertIn("publish_launch_id: room-launch:retry", envelope)
        self.assertIn("launch_id: room-launch:retry", envelope)
        self.assertIn("launch_qualified_handle: corp/priya", envelope)
        self.assertIn("thread_participants_json:", envelope)

    def test_retry_peer_fanout_requires_known_publish(self) -> None:
        with self.assertRaisesRegex(ValueError, "publish not found"):
            common.retry_peer_fanout("mattermost-publish-missing")

    def test_peer_delivery_exit_code_flags_partial_failures(self) -> None:
        healthy = {"peer_delivery": {"phase": "peer_fanout_complete", "status": "delivered", "targets": []}}
        broken = {
            "peer_delivery": {
                "phase": "peer_fanout_partial_failure",
                "status": "partial_failure",
                "targets": [{"session_name": "corp--priya", "status": "failed_retryable"}],
            }
        }

        self.assertEqual(common.peer_delivery_exit_code(healthy), 0)
        self.assertEqual(common.peer_delivery_exit_code(broken), 2)

    # ------------------------------------------------------------------
    # mattermost http plumbing
    # ------------------------------------------------------------------

    def test_mattermost_api_request_retries_after_rate_limit(self) -> None:
        os.environ["GC_MATTERMOST_URL"] = "https://mattermost.test"
        rate_limited = urllib.error.HTTPError(
            "https://mattermost.test/api/v4/channels/1",
            429,
            "Too Many Requests",
            {"Retry-After": "0"},
            io.BytesIO(b'{"id": "api.context.rate_limit"}'),
        )
        success = mock.Mock()
        success.__enter__ = mock.Mock(return_value=mock.Mock(read=mock.Mock(return_value=b'{"ok": true}')))
        success.__exit__ = mock.Mock(return_value=False)

        with mock.patch.object(
            common.urllib.request, "urlopen", side_effect=[rate_limited, success]
        ) as urlopen, mock.patch.object(common.time, "sleep") as sleep:
            payload = common.mattermost_api_request("GET", "/channels/1", bot_token="token")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(0.0)

    def test_mattermost_api_request_raises_with_status_code(self) -> None:
        os.environ["GC_MATTERMOST_URL"] = "https://mattermost.test"
        not_found = urllib.error.HTTPError(
            "https://mattermost.test/api/v4/channels/1",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"message": "missing"}'),
        )

        with mock.patch.object(common.urllib.request, "urlopen", side_effect=not_found):
            with self.assertRaises(common.MattermostAPIError) as caught:
                common.mattermost_api_request("GET", "/channels/1", bot_token="token")

        self.assertEqual(caught.exception.status_code, 404)

    def test_mattermost_api_base_requires_site_url(self) -> None:
        with self.assertRaisesRegex(common.MattermostAPIError, "site_url is not configured"):
            common.mattermost_api_base()

    def test_mattermost_websocket_url_upgrades_scheme(self) -> None:
        os.environ["GC_MATTERMOST_URL"] = "https://mattermost.test"
        self.assertEqual(common.mattermost_websocket_url(), "wss://mattermost.test/api/v4/websocket")

        os.environ["GC_MATTERMOST_URL"] = "http://mattermost.test"
        self.assertEqual(common.mattermost_websocket_url(), "ws://mattermost.test/api/v4/websocket")

    def test_mattermost_retry_after_seconds_prefers_retry_after_header(self) -> None:
        exc = urllib.error.HTTPError("https://mattermost.test", 429, "rate", {"Retry-After": "2.5"}, io.BytesIO(b""))
        self.assertEqual(common.mattermost_retry_after_seconds(exc), 2.5)

    def test_mattermost_retry_after_seconds_falls_back_to_rate_limit_reset(self) -> None:
        exc = urllib.error.HTTPError("https://mattermost.test", 429, "rate", {"X-RateLimit-Reset": "3"}, io.BytesIO(b""))
        self.assertEqual(common.mattermost_retry_after_seconds(exc), 3.0)

    def test_mattermost_retry_after_seconds_defaults_to_one_second(self) -> None:
        exc = urllib.error.HTTPError("https://mattermost.test", 429, "rate", {}, io.BytesIO(b""))
        self.assertEqual(common.mattermost_retry_after_seconds(exc), 1.0)

    # ------------------------------------------------------------------
    # policy gates
    # ------------------------------------------------------------------

    def test_policy_reason_enforces_team_channel_and_role_allowlists(self) -> None:
        config = common.import_app_config(
            common.load_config(),
            {
                "site_url": "https://mattermost.test",
                "team_allowlist": [TEAM_ID],
                "channel_allowlist": [CHANNEL_ID],
                "channel_role_allowlist": [common.CHANNEL_ADMIN_ROLE],
            },
        )

        self.assertEqual(common.policy_reason(config, TEAM_ID, CHANNEL_ID, "channel_user channel_admin"), "")
        self.assertEqual(common.policy_reason(config, OTHER_TEAM_ID, CHANNEL_ID, ["channel_admin"]), "team_not_allowed")
        self.assertEqual(common.policy_reason(config, TEAM_ID, OTHER_CHANNEL_ID, ["channel_admin"]), "channel_not_allowed")
        self.assertEqual(common.policy_reason(config, TEAM_ID, CHANNEL_ID, ["channel_user"]), "channel_role_not_allowed")
        self.assertEqual(common.policy_reason(config, TEAM_ID, CHANNEL_ID, []), "channel_membership_required")

    def test_policy_reason_allows_everything_without_allowlists(self) -> None:
        self.assertEqual(common.policy_reason(common.load_config(), TEAM_ID, CHANNEL_ID, []), "")


if __name__ == "__main__":
    unittest.main()
