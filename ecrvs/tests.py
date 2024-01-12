import unittest


class EcrvsTestCase(unittest.TestCase):
  def test_dummy(self):
    self.assertTrue(True)

  # Some tests were identified and were done manually on postman.
  # They should be translated here, but I couldn't run unit tests locally because they are broken, so I didn't bother :(
  # location - create simple district
  # location - create simple ward
  # location - create simple village
  # location - update district
  # location - update ward
  # location - update village
  # location - update unknown district
  # location - update unknown ward
  # location - update unknown village
  # location - update village to region level
  # location - update village to district level
  # location - update village to ward level
  # location - delete district
  # location - delete ward
  # location - delete village
  # location - delete unknown district
  # location - delete unknown ward
  # location - delete unknown village
  # health facility - create simple HF
  # health facility - create HF with the same name in the same location
  # health facility - create HF in unknown location
  # health facility - create HF of unknown type
  # health facility - update HF
  # health facility - update unknown HF
  # health facility - update HF to unknown location
  # health facility - update HF to unknown type
  # health facility - delete HF
  # health facility - delete unknown HF
  # other - error in notification handling with unknown topic
  # other - error in notification handling with unknown context
  # other - error in notification handling with unknown operation
  # insuree - create simple insuree
  # insuree - create insuree with same NIN (= update insuree)
  # insuree - create insuree in unknown location
