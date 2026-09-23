import unittest

from app import extract_intake_fields, normalize_iqi_placement


REPORT_TEXT = """工程名称
福建漳州核电厂1、2号机组核岛安装工程
实施单位
中核二三漳州项目部质检部试验室
验收标准/级别
1516AT0012/B/03部件名称
规格mm
762×7.92/Φ762×7.92
等轴图号
透照方式
中心透照
透照厚度
7.92
焦距
胶片透照技术
单片
胶片牌号/等级
像质计型号
10FEJB
像质计位置
□源侧
片侧
检测技术等级
设备型号/编号
YG-75S/0323SE003092
焦点尺寸
操作者
李世吉
处理
日期
2023-07-162023-7-16
"""


class IntakeFieldExtractionTest(unittest.TestCase):
    def test_checked_film_side_is_preferred_when_empty_source_box_is_recognized(self):
        self.assertEqual("片侧", normalize_iqi_placement("□源侧\n片侧"))

    def test_extracts_and_normalizes_intake_confirmation_fields(self):
        fields = extract_intake_fields([], REPORT_TEXT)
        values = {field["key"]: field["value"] for field in fields}

        self.assertEqual(
            "福建漳州核电厂1、2号机组核岛安装工程",
            values["projectName"],
        )
        self.assertEqual("YG-75S/0323SE003092", values["equipmentModelNo"])
        self.assertEqual("1516AT0012/B", values["acceptanceStandard"])
        self.assertEqual("III级", values["acceptLevel"])
        self.assertEqual("2023-07-16", values["inspectionDate"])
        self.assertEqual("φ762×7.92/φ762×7.92", values["specification"])
        self.assertEqual("中心透照", values["exposureMethod"])
        self.assertEqual("片侧", values["iqiPlacement"])
        self.assertEqual("10FEJB", values["iqiModelQuantity"])
        self.assertEqual("7.92", values["penetrationThicknessMm"])
        self.assertEqual("单片", values["singleDoubleFilmTechnique"])
        self.assertEqual("李世吉", values["inspector"])
        self.assertEqual("中核二三漳州项目部质检部试验室", values["inspectionUnit"])


if __name__ == "__main__":
    unittest.main()
