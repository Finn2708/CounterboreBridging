"""User-facing strings and their translations. English is the key and the fallback."""

import adsk.core

_L = adsk.core.UserLanguages

_TRANSLATIONS = {
    _L.ChinesePRCLanguage: {
        "Counterbore Bridge": "沉孔搭桥",
        "Edit Counterbore Bridge": "编辑沉孔搭桥",
        "Adds bridging layers below counterbores, so they print without support.":
            "在沉头孔下方添加搭桥层，使其无需支撑即可打印。",
        "Counterbore floors": "沉头孔底面",
        "Select the floor faces of the counterbores (the faces with the hole).": "请选择沉头孔底面（带孔的面）。",
        "Reference": "参考方向",
        "Optional: straight edge, sketch line or axis the first bridges run along.":
            "可选：第一层搭桥所沿的直边、草图直线或轴。",
        "Angle": "角度",
        "Layer height": "层高",
        "Layers": "层数",
        "Layers from hole shape": "根据孔形确定层数",
        "One layer per straight-edge direction of the hole, e.g. 3 for a hex hole. Round holes and slots get 2.":
            "孔的每个直边方向对应一层，例如六角孔为3层。圆孔和长圆孔为2层。",
        "Rotates the bridges of round holes, or of all holes when the layers are set manually.":
            "旋转圆孔的搭桥；手动设置层数时旋转所有孔的搭桥。",
    },
    _L.ChineseTaiwanLanguage: {
        "Counterbore Bridge": "沉頭孔搭橋",
        "Edit Counterbore Bridge": "編輯沉頭孔搭橋",
        "Adds bridging layers below counterbores, so they print without support.":
            "在沉頭孔下方添加搭橋層，使其無需支撐即可列印。",
        "Counterbore floors": "沉頭孔底面",
        "Select the floor faces of the counterbores (the faces with the hole).": "請選擇沉頭孔底面（帶孔的面）。",
        "Reference": "參考方向",
        "Optional: straight edge, sketch line or axis the first bridges run along.":
            "可選：第一層搭橋所沿的直邊、草圖直線或軸。",
        "Angle": "角度",
        "Layer height": "層高",
        "Layers": "層數",
        "Layers from hole shape": "依孔形決定層數",
        "One layer per straight-edge direction of the hole, e.g. 3 for a hex hole. Round holes and slots get 2.":
            "孔的每個直邊方向對應一層，例如六角孔為3層。圓孔和長圓孔為2層。",
        "Rotates the bridges of round holes, or of all holes when the layers are set manually.":
            "旋轉圓孔的搭橋；手動設定層數時旋轉所有孔的搭橋。",
    },
    _L.GermanLanguage: {
        "Counterbore Bridge": "Senkungsbrücke",
        "Edit Counterbore Bridge": "Senkungsbrücke bearbeiten",
        "Adds bridging layers below counterbores, so they print without support.":
            "Fügt unter Senkungen Brückenschichten hinzu, damit sie ohne Stützstruktur druckbar sind.",
        "Counterbore floors": "Senkungsböden",
        "Select the floor faces of the counterbores (the faces with the hole).":
            "Böden der Senkungen auswählen (die Flächen mit der Bohrung).",
        "Reference": "Referenz",
        "Optional: straight edge, sketch line or axis the first bridges run along.":
            "Optional: gerade Kante, Skizzenlinie oder Achse, entlang der die ersten Brücken verlaufen.",
        "Angle": "Winkel",
        "Layer height": "Schichthöhe",
        "Layers": "Schichten",
        "Layers from hole shape": "Schichten aus Bohrungsform",
        "One layer per straight-edge direction of the hole, e.g. 3 for a hex hole. Round holes and slots get 2.":
            "Eine Schicht pro Richtung gerader Bohrungskanten, z. B. 3 bei einer Sechskantbohrung. "
            "Runde Bohrungen und Langlöcher erhalten 2.",
        "Rotates the bridges of round holes, or of all holes when the layers are set manually.":
            "Dreht die Brücken runder Bohrungen, bzw. aller Bohrungen bei manueller Schichtanzahl.",
    },
}


def tr(text: str) -> str:
    language = adsk.core.Application.get().preferences.generalPreferences.userLanguage
    return _TRANSLATIONS.get(language, {}).get(text, text)
