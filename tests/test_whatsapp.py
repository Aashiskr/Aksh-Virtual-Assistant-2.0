import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.actions.communication import CommunicationActions
from backend.actions.whatsapp import (
    CALL_LABELS,
    END_CALL_LABELS,
    WhatsAppController,
)
from backend.actions.whatsapp_contact_finder import (
    _results_container,
    find_contact_control,
)
from backend.actions.whatsapp_controls import find_edit
from backend.actions.whatsapp_names import (
    base_contact_name,
    choose_contact_name,
    display_contact_name,
    normalize_contact_name,
    phonetic_contact_name,
)
from backend.actions.whatsapp_phone import normalize_whatsapp_number
from backend.actions.whatsapp_search import contact_search_queries
from backend.actions.whatsapp_target import editor_matches_target
from backend.brain.fallback import local_intent
from backend.config import AkshSettings


class WhatsAppRoutingTests(unittest.TestCase):
    def test_hinglish_web_message_intent(self):
        result = local_intent(
            "whatsapp web par Rahul ko message karo ki meeting 5 baje hai"
        )
        action = result.actions[0]
        self.assertEqual(action.name, "whatsapp_message")
        self.assertEqual(action.parameters["platform"], "web")
        self.assertEqual(action.parameters["contact"], "rahul")
        self.assertEqual(action.parameters["message"], "meeting 5 baje hai")

    def test_normal_whatsapp_defaults_to_desktop(self):
        result = local_intent("message to Rahul saying hello")
        self.assertEqual(result.actions[0].parameters["platform"], "desktop")

    def test_actions_pass_platform_to_controller(self):
        actions = CommunicationActions(AkshSettings())
        actions.whatsapp = Mock()
        result = actions.whatsapp_message(
            {"contact": "Rahul", "message": "Hello", "platform": "web"}
        )
        actions.whatsapp.send_message.assert_called_once_with(
            "Rahul", "Hello", "web"
        )
        self.assertTrue(result.success)

    def test_end_call_action_passes_platform_to_controller(self):
        actions = CommunicationActions(AkshSettings())
        actions.whatsapp = Mock()
        result = actions.whatsapp_end_call({"platform": "web"})
        actions.whatsapp.end_call.assert_called_once_with("web")
        self.assertTrue(result.success)

    def test_call_reuses_shared_contact_matching_flow(self):
        controller = WhatsAppController()
        window = Mock()
        button = Mock()
        controller._get_window = Mock(return_value=(window, True))
        controller._open_contact = Mock()
        controller._wait_for_button = Mock(return_value=button)
        controller._click = Mock()
        controller._start_call("Prakash", "desktop")
        controller._open_contact.assert_called_once_with(
            window,
            "Prakash",
            prefer_first=True,
            match_timeout=2.5,
        )
        controller._click.assert_called_once_with(button)

    def test_call_by_saved_number_uses_first_search_result(self):
        controller = WhatsAppController()
        window = Mock()
        button = Mock()
        controller._get_window = Mock(return_value=(window, True))
        controller._open_contact = Mock(return_value=Mock())
        controller._open_phone_chat = Mock()
        controller._wait_for_button = Mock(return_value=button)
        controller._click = Mock()

        controller._start_call("9000000001", "desktop")

        controller._open_contact.assert_called_once_with(
            window,
            "9000000001",
            prefer_first=True,
            allow_missing=True,
            match_timeout=4,
        )
        controller._open_phone_chat.assert_not_called()
        controller._click.assert_called_once_with(button)

    def test_unsaved_number_falls_back_to_direct_whatsapp_chat(self):
        controller = WhatsAppController()
        initial_window = Mock()
        direct_window = Mock()
        button = Mock()
        controller._get_window = Mock(return_value=(initial_window, True))
        controller._open_contact = Mock(return_value=None)
        controller._open_phone_chat = Mock(return_value=direct_window)
        controller._wait_for_button = Mock(return_value=button)
        controller._click = Mock()

        controller._start_call("9000000001", "desktop")

        controller._open_phone_chat.assert_called_once_with(
            "919000000001",
            "desktop",
        )
        controller._wait_for_button.assert_called_once_with(
            direct_window,
            CALL_LABELS,
            timeout=8,
        )

    @patch("backend.actions.whatsapp_calls.find_button")
    def test_end_call_clicks_ringing_or_connected_control(self, find_button):
        controller = WhatsAppController()
        controller._active_call_platform = "desktop"
        window = Mock()
        window.handle = 42
        button = Mock()
        controller._existing_windows_for_call = Mock(
            side_effect=lambda platform, **_: (
                [window] if platform == "desktop" else []
            )
        )
        controller._focus = Mock()
        controller._click = Mock()
        find_button.side_effect = [button, None]

        controller._end_call("desktop")

        controller._focus.assert_called_once_with(window)
        controller._click.assert_called_once_with(button)
        self.assertIsNone(controller._active_call_platform)
        self.assertIn("Cancel voice call", END_CALL_LABELS)
        self.assertIn("End call", END_CALL_LABELS)

    @patch("backend.actions.whatsapp_calls.find_button", return_value=None)
    def test_end_call_does_not_report_success_without_control(self, find_button):
        controller = WhatsAppController()
        controller._existing_windows_for_call = Mock(return_value=[])
        controller._wait_for = Mock(return_value=None)

        with self.assertRaisesRegex(RuntimeError, "end button nahi mila"):
            controller._end_call("desktop")

    def test_indian_and_international_numbers_are_normalized(self):
        self.assertEqual(
            normalize_whatsapp_number("9000000001"),
            "919000000001",
        )
        self.assertEqual(
            normalize_whatsapp_number("+1 (415) 555-2671"),
            "14155552671",
        )
        self.assertIsNone(normalize_whatsapp_number("Sudheer Sir"))

    def test_custom_default_country_code_is_supported(self):
        controller = WhatsAppController("44")
        self.assertEqual(controller.default_country_code, "44")
        self.assertEqual(
            normalize_whatsapp_number(
                "9000000002",
                default_country_code=controller.default_country_code,
            ),
            "449000000002",
        )

    def test_indian_name_search_builds_bounded_phonetic_variants(self):
        queries = contact_search_queries("Sudhir Sir")
        self.assertEqual(queries[:3], ["sudhir", "sudheer", "sudeer"])
        self.assertLessEqual(len(queries), 8)

    @patch("backend.actions.whatsapp.find_target_editor")
    @patch("backend.actions.whatsapp.find_contact_control")
    def test_contact_search_observes_failure_then_retries_variant(
        self,
        find_contact,
        find_target_editor,
    ):
        controller = WhatsAppController()
        window = Mock()
        search = Mock()
        selected = Mock()
        editor = Mock()
        controller._get_search_edit = Mock(return_value=search)
        controller._replace_text = Mock()
        controller._click = Mock()
        controller._wait_for_edit = Mock(return_value=editor)
        controller._wait_for = Mock(side_effect=lambda function, timeout: function())
        find_contact.side_effect = [None, None, selected]
        find_target_editor.return_value = editor

        result = controller._open_contact(
            window,
            "Sudhir Sir",
            prefer_first=True,
            match_timeout=0,
        )

        self.assertIs(result, editor)
        self.assertEqual(
            [
                call.args[2]
                for call in controller._replace_text.call_args_list
            ],
            ["sudhir", "sudheer", "sudeer"],
        )
        controller._click.assert_called_once_with(selected)

    def test_contact_selection_retries_when_invoke_leaves_old_chat_open(self):
        controller = WhatsAppController()
        window = Mock()
        search = Mock()
        selected = Mock()
        selected.element_info.name = "+91 98100 37784"
        editor = Mock()
        controller._get_search_edit = Mock(return_value=search)
        controller._replace_text = Mock()
        controller._click = Mock()
        controller._focus = Mock()
        controller._wait_for = Mock(
            side_effect=[selected, None, editor]
        )

        result = controller._open_contact(
            window,
            "9000000003",
            prefer_first=True,
        )

        self.assertIs(result, editor)
        controller._click.assert_called_once_with(selected)
        selected.click_input.assert_called_once_with()

    @patch("backend.actions.whatsapp_contact_finder._result_controls")
    @patch("backend.actions.whatsapp_contact_finder._results_container")
    def test_call_search_selects_top_visible_result(
        self,
        results_container,
        result_controls,
    ):
        def rect(left, top, right, bottom):
            return SimpleNamespace(
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )

        search = Mock()
        search.rectangle.return_value = rect(20, 20, 400, 60)
        window = Mock()
        window.rectangle.return_value = rect(0, 0, 500, 800)
        lower = Mock()
        lower.element_info = SimpleNamespace(name="Sudheer Sharma")
        lower.rectangle.return_value = rect(20, 150, 400, 200)
        lower.is_visible.return_value = True
        top = Mock()
        top.element_info = SimpleNamespace(name="Sudheer Sir")
        top.rectangle.return_value = rect(20, 80, 400, 130)
        top.is_visible.return_value = True
        result_controls.return_value = [lower, top]

        selected = find_contact_control(
            window,
            "Sudheer",
            search,
            prefer_first=True,
        )

        self.assertIs(selected, top)

    @patch("backend.actions.whatsapp_contact_finder._result_controls")
    @patch("backend.actions.whatsapp_contact_finder._results_container")
    def test_number_search_never_selects_unrelated_first_contact(
        self,
        results_container,
        result_controls,
    ):
        def rect(left, top, right, bottom):
            return SimpleNamespace(
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )

        search = Mock()
        search.rectangle.return_value = rect(20, 20, 400, 60)
        window = Mock()
        window.rectangle.return_value = rect(0, 0, 500, 800)
        unrelated = Mock()
        unrelated.element_info = SimpleNamespace(name="Sudhir Sir")
        unrelated.rectangle.return_value = rect(20, 80, 400, 130)
        unrelated.is_visible.return_value = True
        number = Mock()
        number.element_info = SimpleNamespace(name="+91 90000 00003")
        number.rectangle.return_value = rect(20, 150, 400, 200)
        number.is_visible.return_value = True
        result_controls.return_value = [unrelated, number]

        selected = find_contact_control(
            window,
            "9000000003",
            search,
            prefer_first=True,
        )

        self.assertIs(selected, number)

    @patch("backend.actions.whatsapp_contact_finder._result_controls")
    @patch("backend.actions.whatsapp_contact_finder._results_container")
    def test_name_search_skips_clear_and_section_rows(
        self,
        results_container,
        result_controls,
    ):
        def rect(left, top, right, bottom):
            return SimpleNamespace(
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )

        search = Mock()
        search.rectangle.return_value = rect(20, 20, 400, 60)
        window = Mock()
        window.rectangle.return_value = rect(0, 0, 500, 800)

        def row(name, top):
            item = Mock()
            item.element_info = SimpleNamespace(name=name)
            item.rectangle.return_value = rect(20, top, 400, top + 45)
            item.is_visible.return_value = True
            return item

        clear = row("Clear all", 70)
        heading = row("Chats", 120)
        khushi = row(
            "View status Khushi 1:32 pm Last message Starred chat",
            170,
        )
        result_controls.return_value = [clear, heading, khushi]

        selected = find_contact_control(
            window,
            "Khushi",
            search,
            prefer_first=True,
        )

        self.assertIs(selected, khushi)

    def test_number_target_rejects_stale_sudhir_editor(self):
        stale = Mock()
        stale.element_info.name = (
            "Type a message to Sudhir sir Orionn Architect"
        )
        target = Mock()
        target.element_info.name = "Type a message to +91 98100 37784"

        self.assertFalse(
            editor_matches_target(
                stale,
                "9000000003",
                "+91 98100 37784",
            )
        )
        self.assertTrue(
            editor_matches_target(
                target,
                "9000000003",
                "+91 98100 37784",
            )
        )

    def test_results_container_ignores_thin_spacer_below_search(self):
        def rect(left, top, right, bottom):
            return SimpleNamespace(
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )

        search = Mock()
        search.rectangle.return_value = rect(149, 128, 419, 152)
        spacer = Mock()
        spacer.element_info.control_type = "Group"
        spacer.rectangle.return_value = rect(73, 216, 500, 225)
        results = Mock()
        results.element_info.control_type = "Group"
        results.rectangle.return_value = rect(73, 224, 500, 387)
        parent = Mock()
        parent.children.return_value = [spacer, results]
        search.parent.return_value = parent

        self.assertIs(_results_container(search), results)

    @patch("backend.actions.whatsapp_phone_chat.subprocess.Popen")
    def test_unsaved_desktop_number_uses_whatsapp_protocol(self, popen):
        controller = WhatsAppController()
        window = Mock()
        controller._find_desktop_window = Mock(return_value=None)
        controller._wait_for = Mock(return_value=window)
        controller._focus = Mock()

        result = controller._open_phone_chat("919000000001", "desktop")

        self.assertIs(result, window)
        self.assertEqual(
            popen.call_args.args[0],
            [
                "explorer.exe",
                "whatsapp://send?phone=919000000001",
            ],
        )

    def test_unknown_platform_is_desktop(self):
        self.assertEqual(WhatsAppController._platform("normal"), "desktop")
        self.assertEqual(WhatsAppController._platform("web"), "web")

    def test_contact_matching_ignores_trailing_emoji(self):
        self.assertEqual(normalize_contact_name("Prakash 😊"), "prakash")
        self.assertEqual(normalize_contact_name("Prakash ❤️"), "prakash")
        self.assertNotEqual(normalize_contact_name("Prakash Kumar"), "prakash")

    def test_whatsapp_row_metadata_is_not_part_of_contact_name(self):
        row = "Prakash 🦴 2:43 am last message preview"
        self.assertEqual(display_contact_name(row), "Prakash 🦴")
        self.assertEqual(
            display_contact_name(
                "Abhay Kumar SU 11/07/2026 security code changed"
            ),
            "Abhay Kumar SU",
        )

    def test_exact_emoji_name_wins_over_longer_similar_names(self):
        rows = [
            "Prakash 🦴 2:43 am last message",
            "Prakash SU 11/07/2026 security code changed",
            "PRAKASH KUMAR BEHURA",
        ]
        self.assertEqual(choose_contact_name("Prakash", rows), rows[0])

    def test_unique_first_name_can_match_full_saved_name(self):
        self.assertEqual(
            choose_contact_name("Abhay", ["Abhay Kumar SU"]),
            "Abhay Kumar SU",
        )
        self.assertIsNone(
            choose_contact_name(
                "Abhay", ["Abhay Kumar SU", "Abhay Sharma"]
            )
        )

    def test_group_metadata_is_not_treated_as_contact(self):
        group = "Abhay Friends Yesterday someone is also in this group"
        self.assertIsNone(choose_contact_name("Abhay", [group]))

    def test_honorific_and_indian_spelling_variant_match(self):
        self.assertEqual(base_contact_name("Sudhir Sir"), "sudhir")
        self.assertEqual(
            phonetic_contact_name("Sudheer"),
            phonetic_contact_name("Sudhir Sir"),
        )
        self.assertEqual(
            choose_contact_name("Sudhir Sir", ["Sudheer"]),
            "Sudheer",
        )
        self.assertEqual(
            choose_contact_name("Sudheer Sir", ["Sudhir Sir"]),
            "Sudhir Sir",
        )

    def test_hinglish_call_accepts_short_kro_spelling(self):
        result = local_intent("Sudhir Sir ko call kro")
        action = result.actions[0]
        self.assertEqual(action.name, "whatsapp_call")
        self.assertEqual(action.parameters["contact"], "sudhir sir")

    def test_hinglish_end_call_works_while_outgoing_call_is_ringing(self):
        result = local_intent("call cut kr do")
        action = result.actions[0]
        self.assertEqual(action.name, "whatsapp_end_call")
        self.assertEqual(action.parameters["platform"], "desktop")

    def test_whatsapp_web_end_call_preserves_platform(self):
        result = local_intent("whatsapp web call ko kaat do")
        action = result.actions[0]
        self.assertEqual(action.name, "whatsapp_end_call")
        self.assertEqual(action.parameters["platform"], "web")

    def test_phone_number_call_intent_preserves_every_digit(self):
        result = local_intent("9000000001 ko call kro")
        action = result.actions[0]
        self.assertEqual(action.name, "whatsapp_call")
        self.assertEqual(action.parameters["contact"], "9000000001")

    def test_named_duplicate_editor_wins_over_blank_duplicate(self):
        rect = SimpleNamespace(left=10, top=20, right=200, bottom=50)

        def control(name):
            item = Mock()
            item.element_info = SimpleNamespace(name=name)
            item.rectangle.return_value = rect
            item.is_visible.return_value = True
            return item

        blank = control("")
        named = control("Type a message to Sudhir")
        window = Mock()
        window.descendants.return_value = [blank, named]
        self.assertIs(
            find_edit(window, ("Type a message", "Message")),
            named,
        )

    @patch("backend.actions.whatsapp.replace_focused_text")
    @patch.object(WhatsAppController, "_is_foreground", return_value=True)
    @patch.object(WhatsAppController, "_focus")
    def test_typing_reuses_verified_window(
        self, focus, is_foreground, replace_text
    ):
        window = Mock()
        control = Mock()
        WhatsAppController._replace_text(window, control, "hello")
        focus.assert_called_once_with(window)
        control.top_level_parent.assert_not_called()
        control.click_input.assert_called_once_with()
        self.assertEqual(is_foreground.call_count, 2)
        is_foreground.assert_called_with(window)
        replace_text.assert_called_once_with("hello")


if __name__ == "__main__":
    unittest.main()
