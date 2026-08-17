from __future__ import annotations

import io
import json
import os
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import discord_chat_bind as bind_script
import discord_chat_publish as publish_script
import discord_chat_reply_current as reply_current_script
import discord_intake_common as common
import discord_intake_import as import_script
import discord_intake_status as status_script


class DiscordMultiBotCLIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def _import_named_app(self, app_name: str, application_id: str, public_key_byte: str) -> None:
        common.import_app_config(
            common.load_config(),
            {
                "application_id": application_id,
                "public_key": public_key_byte * 32,
            },
            app_name=app_name,
        )

    def test_import_app_selector_preserves_legacy_default_app_and_token(self) -> None:
        default_credential = "default-test-credential"
        named_credential = "ollie-test-credential"

        with redirect_stdout(io.StringIO()):
            legacy_code = import_script.main(
                [
                    "--application-id",
                    "123",
                    "--public-key",
                    "ab" * 32,
                    "--bot-token",
                    default_credential,
                ]
            )

        stdout = io.StringIO()
        with mock.patch.object(common, "discord_api_request", return_value={"id": "456"}), redirect_stdout(stdout):
            named_code = import_script.main(
                [
                    "--app",
                    "ollie",
                    "--application-id",
                    "456",
                    "--public-key",
                    "cd" * 32,
                    "--bot-token",
                    named_credential,
                    "--guild-allowlist",
                    "guild-ollie",
                ]
            )

        self.assertEqual(legacy_code, 0)
        self.assertEqual(named_code, 0)
        config = common.load_config()
        self.assertEqual(config["app"]["application_id"], "123")
        self.assertEqual(config["apps"]["ollie"]["application_id"], "456")
        self.assertEqual(config["apps"]["ollie"]["policy"]["guild_allowlist"], ["guild-ollie"])
        self.assertEqual(common.load_bot_token(), default_credential)
        self.assertEqual(common.load_bot_token("ollie"), named_credential)
        rendered = stdout.getvalue()
        self.assertNotIn(default_credential, rendered)
        self.assertNotIn(named_credential, rendered)
        self.assertTrue(json.loads(rendered)["apps"]["ollie"]["bot_token_present"])

    def test_named_import_rejects_token_for_a_different_application_without_mutation(self) -> None:
        with mock.patch.object(common, "discord_api_request", return_value={"id": "999"}):
            with self.assertRaisesRegex(SystemExit, "authenticated as.*application_id"):
                import_script.main(
                    [
                        "--app",
                        "ollie",
                        "--application-id",
                        "456",
                        "--public-key",
                        "cd" * 32,
                        "--bot-token",
                        "wrong-app-token",
                    ]
                )

        self.assertEqual(common.load_config()["apps"], {})
        self.assertEqual(common.load_bot_token("ollie"), "")

    def test_named_import_reports_authentication_failure_without_leaking_or_mutating(self) -> None:
        credential = "must-not-appear"
        api_error = common.DiscordAPIError(
            f"GET /users/@me rejected {credential}",
            status_code=401,
        )

        with mock.patch.object(common, "discord_api_request", side_effect=api_error):
            with self.assertRaises(SystemExit) as raised:
                import_script.main(
                    [
                        "--app",
                        "ollie",
                        "--application-id",
                        "456",
                        "--public-key",
                        "cd" * 32,
                        "--bot-token",
                        credential,
                    ]
                )

        message = str(raised.exception)
        self.assertIn("failed to authenticate Discord bot token", message)
        self.assertIn("HTTP 401", message)
        self.assertNotIn(credential, message)
        self.assertEqual(common.load_config()["apps"], {})
        self.assertEqual(common.load_bot_token("ollie"), "")

    def test_named_token_rotation_preserves_existing_policy(self) -> None:
        with mock.patch.object(common, "discord_api_request", return_value={"id": "456"}), redirect_stdout(io.StringIO()):
            import_script.main(
                [
                    "--app",
                    "ollie",
                    "--application-id",
                    "456",
                    "--public-key",
                    "cd" * 32,
                    "--bot-token",
                    "first-credential",
                    "--guild-allowlist",
                    "1",
                    "--channel-allowlist",
                    "22",
                    "--role-allowlist",
                    "7",
                ]
            )
            import_script.main(
                [
                    "--app",
                    "ollie",
                    "--application-id",
                    "456",
                    "--public-key",
                    "cd" * 32,
                    "--bot-token",
                    "rotated-credential",
                ]
            )

        policy = common.resolve_app_policy(common.load_config(), "ollie")
        self.assertEqual(policy["guild_allowlist"], ["1"])
        self.assertEqual(policy["channel_allowlist"], ["22"])
        self.assertEqual(policy["role_allowlist"], ["7"])
        self.assertEqual(common.load_bot_token("ollie"), "rotated-credential")

    def test_explicit_empty_named_token_file_fails_without_mutating_existing_identity(self) -> None:
        self._import_named_app("ollie", "456", "cd")
        common.save_bot_token("existing-credential", app_name="ollie")
        empty_token_file = pathlib.Path(self.tempdir.name) / "empty-token"
        empty_token_file.write_text("", encoding="utf-8")

        with self.assertRaisesRegex(SystemExit, "bot token file is empty"):
            import_script.main(
                [
                    "--app",
                    "ollie",
                    "--application-id",
                    "789",
                    "--public-key",
                    "ef" * 32,
                    "--bot-token-file",
                    str(empty_token_file),
                ]
            )

        app = common.resolve_app_config(common.load_config(), "ollie")
        self.assertEqual(app["application_id"], "456")
        self.assertEqual(common.load_bot_token("ollie"), "existing-credential")

    def test_named_import_rejects_application_id_change_even_with_a_matching_token(self) -> None:
        self._import_named_app("ollie", "456", "cd")
        common.save_bot_token("existing-credential", app_name="ollie")

        with mock.patch.object(common, "discord_api_request", return_value={"id": "789"}):
            with self.assertRaisesRegex(SystemExit, "cannot change.*application_id"):
                import_script.main(
                    [
                        "--app",
                        "ollie",
                        "--application-id",
                        "789",
                        "--public-key",
                        "ef" * 32,
                        "--bot-token",
                        "replacement-credential",
                    ]
                )

        app = common.resolve_app_config(common.load_config(), "ollie")
        self.assertEqual(app["application_id"], "456")
        self.assertEqual(common.load_bot_token("ollie"), "existing-credential")

    def test_named_import_rejects_an_orphan_token_file_without_reusing_the_slug(self) -> None:
        common.save_bot_token("orphan-credential", app_name="ollie")

        with self.assertRaisesRegex(SystemExit, "orphan bot token.*new app name"):
            import_script.main(
                [
                    "--app",
                    "ollie",
                    "--application-id",
                    "456",
                    "--public-key",
                    "cd" * 32,
                ]
            )

        self.assertEqual(common.load_config()["apps"], {})
        self.assertEqual(common.load_bot_token("ollie"), "orphan-credential")

    def test_named_import_rolls_back_config_when_token_persistence_fails(self) -> None:
        self._import_named_app("ollie", "456", "cd")
        common.save_bot_token("existing-credential", app_name="ollie")

        with mock.patch.object(common, "discord_api_request", return_value={"id": "456"}), mock.patch.object(
            common,
            "save_bot_token",
            side_effect=[OSError("simulated disk full"), None],
        ):
            with self.assertRaisesRegex(SystemExit, "failed to save Discord app credentials"):
                import_script.main(
                    [
                        "--app",
                        "ollie",
                        "--application-id",
                        "456",
                        "--public-key",
                        "ef" * 32,
                        "--bot-token",
                        "replacement-credential",
                    ]
                )

        app = common.resolve_app_config(common.load_config(), "ollie")
        self.assertEqual(app["application_id"], "456")
        self.assertEqual(app["public_key"], "cd" * 32)
        self.assertEqual(common.load_bot_token("ollie"), "existing-credential")

    def test_bind_selector_keeps_default_and_named_room_bindings_independent(self) -> None:
        self._import_named_app("ollie", "456", "cd")

        with redirect_stdout(io.StringIO()):
            legacy_code = bind_script.main(["--kind", "room", "--guild-id", "1", "22", "legacy.session"])
            named_code = bind_script.main(
                [
                    "--kind",
                    "room",
                    "--app",
                    "ollie",
                    "--guild-id",
                    "1",
                    "22",
                    "teams.lead",
                ]
            )

        self.assertEqual(legacy_code, 0)
        self.assertEqual(named_code, 0)
        config = common.load_config()
        legacy = common.resolve_chat_binding(config, "room:22")
        named = common.resolve_chat_binding(config, "room:22@app:ollie")
        self.assertEqual(legacy["session_names"], ["legacy.session"])
        self.assertNotIn("app", legacy)
        self.assertEqual(named["session_names"], ["teams.lead"])
        self.assertEqual(named["app"], "ollie")

    def test_bind_selector_creates_named_dm_binding(self) -> None:
        self._import_named_app("ollie", "456", "cd")

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = bind_script.main(["--kind", "dm", "--app", "ollie", "55", "teams.lead"])

        self.assertEqual(code, 0)
        binding = common.resolve_chat_binding(common.load_config(), "dm:55@app:ollie")
        self.assertEqual(binding["id"], "dm:55@app:ollie")
        self.assertEqual(binding["app"], "ollie")
        self.assertEqual(json.loads(stdout.getvalue())["session_names"], ["teams.lead"])

    def test_named_bind_rejects_a_guild_outside_its_policy_without_mutation(self) -> None:
        common.import_app_config(
            common.load_config(),
            {
                "application_id": "456",
                "public_key": "cd" * 32,
                "guild_allowlist": ["1"],
                "channel_allowlist": ["22"],
            },
            app_name="ollie",
        )

        with mock.patch.object(common, "discord_api_request") as discord_api_request:
            with self.assertRaisesRegex(SystemExit, "guild_not_allowed"):
                bind_script.main(
                    ["--kind", "room", "--app", "ollie", "--guild-id", "9", "22", "teams.lead"]
                )

        discord_api_request.assert_not_called()
        self.assertIsNone(common.resolve_chat_binding(common.load_config(), "room:22@app:ollie"))

    def test_named_bind_accepts_a_thread_under_its_allowed_parent(self) -> None:
        named_credential = "ollie-test-credential"
        common.import_app_config(
            common.load_config(),
            {
                "application_id": "456",
                "public_key": "cd" * 32,
                "guild_allowlist": ["1"],
                "channel_allowlist": ["22"],
            },
            app_name="ollie",
        )
        common.save_bot_token(named_credential, app_name="ollie")

        with mock.patch.object(
            common,
            "discord_api_request",
            return_value={"id": "222", "guild_id": "1", "type": 11, "parent_id": "22"},
        ) as discord_api_request, redirect_stdout(io.StringIO()):
            code = bind_script.main(
                ["--kind", "room", "--app", "ollie", "--guild-id", "1", "222", "teams.lead"]
            )

        self.assertEqual(code, 0)
        discord_api_request.assert_called_once_with(
            "GET",
            "/channels/222",
            bot_token=named_credential,
        )
        binding = common.resolve_chat_binding(common.load_config(), "room:222@app:ollie")
        assert binding is not None
        self.assertEqual(binding["thread_parent_id"], "22")

    def test_named_bind_rejects_a_forged_guild_id_using_discord_channel_scope(self) -> None:
        named_credential = "ollie-test-credential"
        common.import_app_config(
            common.load_config(),
            {
                "application_id": "456",
                "public_key": "cd" * 32,
                "guild_allowlist": ["1"],
            },
            app_name="ollie",
        )
        common.save_bot_token(named_credential, app_name="ollie")

        with mock.patch.object(
            common,
            "discord_api_request",
            return_value={"id": "33", "guild_id": "9", "type": 0},
        ) as discord_api_request:
            with self.assertRaisesRegex(SystemExit, "guild"):
                bind_script.main(
                    ["--kind", "room", "--app", "ollie", "--guild-id", "1", "33", "teams.lead"]
                )

        discord_api_request.assert_called_once_with("GET", "/channels/33", bot_token=named_credential)
        self.assertIsNone(common.resolve_chat_binding(common.load_config(), "room:33@app:ollie"))

    def test_default_bind_verifies_channel_scope_when_top_level_policy_is_restricted(self) -> None:
        default_credential = "default-test-credential"
        common.import_app_config(
            common.load_config(),
            {
                "application_id": "123",
                "public_key": "ab" * 32,
                "guild_allowlist": ["1"],
                "channel_allowlist": ["22"],
            },
        )
        common.save_bot_token(default_credential)

        with mock.patch.object(
            common,
            "discord_api_request",
            return_value={"id": "22", "guild_id": "1", "type": 0},
        ) as discord_api_request, redirect_stdout(io.StringIO()):
            code = bind_script.main(["--kind", "room", "22", "teams.lead"])

        self.assertEqual(code, 0)
        discord_api_request.assert_called_once_with("GET", "/channels/22", bot_token=default_credential)
        binding = common.resolve_chat_binding(common.load_config(), "room:22")
        assert binding is not None
        self.assertEqual(binding["guild_id"], "1")

    def test_publish_selector_uses_named_binding_and_named_app_credential(self) -> None:
        default_credential = "default-test-credential"
        named_credential = "ollie-test-credential"
        common.save_bot_token(default_credential)
        self._import_named_app("ollie", "456", "cd")
        common.save_bot_token(named_credential, app_name="ollie")
        common.set_chat_binding(common.load_config(), "room", "22", ["legacy.session"], guild_id="1")
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["teams.lead"],
            guild_id="1",
            app_name="ollie",
        )
        effective_credentials: list[str] = []

        def fake_discord_api_request(
            method: str,
            path: str,
            payload: object = None,
            bot_token: str | None = None,
        ) -> dict[str, str]:
            del method, path, payload
            effective_credentials.append(bot_token or common.load_bot_token())
            return {"id": f"msg-{len(effective_credentials)}"}

        with mock.patch.object(common, "discord_api_request", side_effect=fake_discord_api_request):
            with redirect_stdout(io.StringIO()):
                legacy_code = publish_script.main(["--binding", "room:22", "--body", "legacy hello"])
                named_code = publish_script.main(
                    ["--binding", "room:22", "--app", "ollie", "--body", "named hello"]
                )

        self.assertEqual(legacy_code, 0)
        self.assertEqual(named_code, 0)
        self.assertEqual(effective_credentials, [default_credential, named_credential])
        publishes = sorted(common.list_recent_chat_publishes(limit=5), key=lambda item: item["remote_message_id"])
        self.assertEqual(publishes[0]["binding_id"], "room:22")
        self.assertEqual(publishes[0].get("app", ""), "")
        self.assertEqual(publishes[1]["binding_id"], "room:22@app:ollie")
        self.assertEqual(publishes[1]["app"], "ollie")

    def test_publish_without_selector_rejects_ambiguous_named_bindings(self) -> None:
        self._import_named_app("ollie", "456", "cd")
        self._import_named_app("olivia", "789", "ef")
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["teams.lead"],
            guild_id="1",
            app_name="ollie",
        )
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["teams.pm"],
            guild_id="1",
            app_name="olivia",
        )

        with self.assertRaisesRegex(SystemExit, r"(?i)ambiguous.*--app"):
            publish_script.main(["--binding", "room:22", "--body", "must choose"])

    def test_named_publish_rejects_a_binding_outside_its_channel_policy(self) -> None:
        common.import_app_config(
            common.load_config(),
            {
                "application_id": "456",
                "public_key": "cd" * 32,
                "guild_allowlist": ["1"],
                "channel_allowlist": ["22"],
            },
            app_name="ollie",
        )
        common.save_bot_token("ollie-test-credential", app_name="ollie")
        common.set_chat_binding(
            common.load_config(),
            "room",
            "33",
            ["teams.lead"],
            guild_id="1",
            app_name="ollie",
            channel_metadata={"channel_type": 0},
        )

        with mock.patch.object(
            common,
            "discord_api_request",
            return_value={"id": "33", "guild_id": "1", "type": 0},
        ) as discord_api_request:
            with self.assertRaisesRegex(SystemExit, "channel_not_allowed"):
                publish_script.main(
                    ["--binding", "room:33", "--app", "ollie", "--body", "must not publish"]
                )

        discord_api_request.assert_called_once_with(
            "GET",
            "/channels/33",
            bot_token="ollie-test-credential",
        )

    def test_default_publish_enforces_top_level_channel_policy_against_discord_scope(self) -> None:
        default_credential = "default-test-credential"
        common.import_app_config(
            common.load_config(),
            {
                "application_id": "123",
                "public_key": "ab" * 32,
                "guild_allowlist": ["1"],
                "channel_allowlist": ["22"],
            },
        )
        common.save_bot_token(default_credential)
        common.set_chat_binding(
            common.load_config(),
            "room",
            "33",
            ["teams.lead"],
            guild_id="1",
            channel_metadata={"channel_type": 0},
        )

        with mock.patch.object(
            common,
            "discord_api_request",
            return_value={"id": "33", "guild_id": "1", "type": 0},
        ) as discord_api_request:
            with self.assertRaisesRegex(SystemExit, "channel_not_allowed"):
                publish_script.main(["--binding", "room:33", "--body", "must not publish"])

        discord_api_request.assert_called_once_with("GET", "/channels/33", bot_token=default_credential)

    def test_reply_current_inherits_the_named_app_from_ingress_binding(self) -> None:
        named_credential = "ollie-test-credential"
        self._import_named_app("ollie", "456", "cd")
        common.save_bot_token(named_credential, app_name="ollie")
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["teams.lead"],
            guild_id="1",
            app_name="ollie",
        )
        discord_calls: list[tuple[str, str, str]] = []

        def fake_discord_api_request(
            method: str,
            path: str,
            payload: object = None,
            bot_token: str | None = None,
        ) -> dict[str, str]:
            del payload
            discord_calls.append((method, path, bot_token or ""))
            if method == "GET":
                return {"id": "222", "parent_id": "22"}
            return {"id": "reply-1"}

        with mock.patch.object(
            common,
            "find_latest_discord_reply_context",
            return_value={
                "kind": "discord_human_message",
                "ingress_receipt_id": "in-202-app-ollie",
                "publish_binding_id": "room:22@app:ollie",
                "publish_conversation_id": "222",
                "publish_trigger_id": "202",
                "publish_reply_to_discord_message_id": "202",
            },
        ), mock.patch.object(common, "discord_api_request", side_effect=fake_discord_api_request):
            with redirect_stdout(io.StringIO()):
                code = reply_current_script.main(["--body", "same bot reply"])

        self.assertEqual(code, 0)
        self.assertEqual(
            discord_calls,
            [
                ("GET", "/channels/222", named_credential),
                ("POST", "/channels/222/messages", named_credential),
            ],
        )
        record = common.list_recent_chat_publishes(limit=1)[0]
        self.assertEqual(record["app"], "ollie")
        self.assertEqual(record["binding_id"], "room:22@app:ollie")
        self.assertEqual(record["conversation_id"], "222")

    def test_reply_current_rejects_a_stale_named_app_without_calling_discord(self) -> None:
        self._import_named_app("ollie", "456", "cd")
        common.set_chat_binding(
            common.load_config(),
            "room",
            "22",
            ["teams.lead"],
            guild_id="1",
            app_name="ollie",
        )
        config = common.load_config()
        del config["apps"]["ollie"]
        common.save_config(config)

        with mock.patch.object(
            common,
            "find_latest_discord_reply_context",
            return_value={
                "kind": "discord_human_message",
                "publish_binding_id": "room:22@app:ollie",
                "publish_conversation_id": "22",
                "publish_reply_to_discord_message_id": "202",
            },
        ), mock.patch.object(common, "discord_api_request") as discord_api_request:
            with self.assertRaisesRegex(SystemExit, "unknown Discord app 'ollie'"):
                reply_current_script.main(["--body", "must not publish"])

        discord_api_request.assert_not_called()

    def test_status_text_exposes_default_and_named_app_health_without_credentials(self) -> None:
        default_credential = "default-test-credential"
        named_credential = "ollie-test-credential"
        common.import_app_config(
            common.load_config(),
            {"application_id": "123", "public_key": "ab" * 32},
        )
        self._import_named_app("ollie", "456", "cd")
        self._import_named_app("olivia", "789", "ef")
        common.save_bot_token(default_credential)
        common.save_bot_token(named_credential, app_name="ollie")
        common.save_gateway_status({"state": "ready", "routed_messages": 4, "failed_messages": 1})
        common.save_gateway_status({"state": "reconnecting", "ignored_messages": 2}, app_name="ollie")
        common.save_gateway_status({"state": "failed", "dropped_messages": 3}, app_name="olivia")

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = status_script.main([])

        self.assertEqual(code, 0)
        rendered = stdout.getvalue()
        self.assertIn("Apps:", rendered)
        self.assertIn("default", rendered)
        self.assertIn("ollie", rendered)
        self.assertIn("olivia", rendered)
        self.assertIn("ready", rendered)
        self.assertIn("reconnecting", rendered)
        self.assertIn("failed", rendered)
        self.assertIn("present", rendered)
        self.assertIn("missing", rendered)
        self.assertIn("routed=4", rendered)
        self.assertIn("ignored=2", rendered)
        self.assertIn("failed=1", rendered)
        self.assertIn("dropped=3", rendered)
        self.assertNotIn(default_credential, rendered)
        self.assertNotIn(named_credential, rendered)


if __name__ == "__main__":
    unittest.main()
