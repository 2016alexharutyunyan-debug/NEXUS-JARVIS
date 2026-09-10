import json
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtGui import QImage, QColor
from screen_agent import validate_proposal, pixel_target, same_screen, Frame, ScreenWorker, ScreenAgent


class ScreenTests(unittest.TestCase):
    def test_unknown_or_unbounded_actions_rejected(self):
        for action in ({'kind':'shell', 'command':'anything'}, {'kind':'click','x':2,'y':0},
                       {'kind':'click','x':float('nan'),'y':0}, {'kind':'click','x':True,'y':0},
                       {'kind':'key','key':'win'}, {'kind':'type','text':'a\nb'},
                       {'kind':'scroll','amount':100}, {'kind':'type','text':'x'*301}):
            with self.assertRaises(ValueError):
                validate_proposal({'reply':'test','action':action})

    def test_proposal_strips_extra_fields(self):
        result = validate_proposal({'reply':'test','action':{'kind':'click','x':.5,'y':.5,'shell':'no'}})
        self.assertNotIn('shell', result['action'])

    def test_monitor_mapping_handles_negative_coordinates(self):
        self.assertEqual(pixel_target({'x':0,'y':0}, (-1920,0,0,1080)), (-1920,0))
        self.assertEqual(pixel_target({'x':1,'y':1}, (-1920,0,0,1080)), (-1,1079))

    def test_changed_image_or_foreground_rejected(self):
        image = QImage(100,100,QImage.Format.Format_RGB32)
        image.fill(QColor('black'))
        frame = Frame(image,b'',10,(0,0,100,100),'App',(0,0,100,100),0)
        other = Frame(image.copy(),b'',10,(0,0,100,100),'App',(0,0,100,100),0)
        self.assertTrue(same_screen(frame, other, {'kind':'click','x':.5,'y':.5}))
        other.image.fill(QColor('white'))
        self.assertFalse(same_screen(frame, other, {'kind':'click','x':.5,'y':.5}))
        other.hwnd=11
        self.assertFalse(same_screen(frame, other, {'kind':'none'}))

    @patch('screen_agent.capture_frame')
    def test_off_mode_never_captures(self, capture):
        owner=MagicMock(active=False)
        ScreenAgent.refresh(owner)
        self.assertFalse(ScreenAgent.submit(owner, 'look'))
        capture.assert_not_called()

    @patch('screen_agent.capture_frame')
    def test_cancel_invalidates_pending_results_and_actions(self, capture):
        owner=MagicMock(active=True,generation=2)
        ScreenAgent.on_result(owner, {'reply':'test','action':{'kind':'click','x':.5,'y':.5}}, None, 1, 'test')
        ScreenAgent.execute(owner, {'kind':'key','key':'enter'}, None, 1)
        capture.assert_not_called()
        owner.reply.emit.assert_not_called()

    @patch('screen_agent.urllib.request.urlopen')
    def test_image_payload_and_credentials_not_in_url(self, urlopen):
        payload={'candidates':[{'content':{'parts':[{'text':json.dumps({'reply':'A test screen','action':{'kind':'none'}})}]}}]}
        urlopen.return_value.__enter__.return_value.read.return_value=json.dumps(payload).encode()
        worker=ScreenWorker('test-key','test-model','What is shown?',b'jpeg-test')
        results=[]
        worker.result.connect(results.append)
        worker.run()
        request=urlopen.call_args.args[0]
        self.assertNotIn('test-key',request.full_url)
        data=json.loads(request.data)
        self.assertEqual(data['contents'][0]['parts'][1]['inlineData']['mimeType'],'image/jpeg')
        self.assertEqual(results[0]['action']['kind'],'none')
        self.assertEqual(worker.key,'')
        self.assertEqual(worker.jpeg,b'')

    def test_disable_clears_frames_and_closes_confirmation(self):
        owner=MagicMock(generation=4)
        ScreenAgent.disable(owner)
        self.assertEqual(owner.generation,5)
        self.assertFalse(owner.active)
        self.assertIsNone(owner.latest)
        owner.dialog.reject.assert_called_once()

    @patch('screen_agent.QMessageBox.question')
    def test_declined_permission_never_starts_capture(self, question):
        from PySide6.QtWidgets import QMessageBox
        question.return_value=QMessageBox.StandardButton.No
        owner=MagicMock(active=False,granted=None)
        ScreenAgent.enable(owner)
        self.assertFalse(owner.granted)
        self.assertFalse(owner.active)
        owner.timer.start.assert_not_called()

    @patch('screen_agent.QMessageBox.question')
    def test_session_grant_starts_sampling_without_repeat_prompt(self, question):
        owner=MagicMock(active=False,granted=True)
        ScreenAgent.enable(owner)
        self.assertTrue(owner.active)
        owner.timer.start.assert_called_once()
        question.assert_not_called()


if __name__ == '__main__':
    unittest.main()
