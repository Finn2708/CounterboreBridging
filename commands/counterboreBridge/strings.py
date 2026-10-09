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
        "Optional: straight edge, sketch line or axis the first bridges run along, instead of the hole's edges.":
            "可选：第一层搭桥所沿的直边、草图直线或轴，代替孔的边方向。",
        "Angle": "角度",
        "Layer height": "层高",
        "Layers": "层数",
        "Layers from hole shape": "根据孔形确定层数",
        "One layer per straight-edge direction of the hole, e.g. 3 for a hex hole. Round holes and slots get 2.":
            "孔的每个直边方向对应一层，例如六角孔为3层。圆孔和长圆孔为2层。",
        "Rotates the bridges from the reference. Without a reference it only applies to round holes "
        "and manual layers, as other holes set their own directions.":
            "相对参考方向旋转搭桥。没有参考方向时，仅对圆孔和手动层数生效，其他孔由自身边方向决定。",
        "Counterbore floor {} not found.": "找不到沉头孔底面 {}。",
        "The reference must be a straight edge, sketch line or construction axis.":
            "参考方向必须是直边、草图直线或构造轴。",
        "The reference is perpendicular to the counterbore floor.": "参考方向垂直于沉头孔底面。",
        "The counterbore floor must be planar and contain a hole.": "沉头孔底面必须是平面且包含孔。",
        "Need at least one layer and a positive layer height.": "至少需要一层，且层高必须大于零。",
    },
    _L.ChineseTaiwanLanguage: {
        "Counterbore Bridge": "沉頭孔搭橋",
        "Edit Counterbore Bridge": "編輯沉頭孔搭橋",
        "Adds bridging layers below counterbores, so they print without support.":
            "在沉頭孔下方添加搭橋層，使其無需支撐即可列印。",
        "Counterbore floors": "沉頭孔底面",
        "Select the floor faces of the counterbores (the faces with the hole).": "請選擇沉頭孔底面（帶孔的面）。",
        "Reference": "參考方向",
        "Optional: straight edge, sketch line or axis the first bridges run along, instead of the hole's edges.":
            "可選：第一層搭橋所沿的直邊、草圖直線或軸，取代孔的邊方向。",
        "Angle": "角度",
        "Layer height": "層高",
        "Layers": "層數",
        "Layers from hole shape": "依孔形決定層數",
        "One layer per straight-edge direction of the hole, e.g. 3 for a hex hole. Round holes and slots get 2.":
            "孔的每個直邊方向對應一層，例如六角孔為3層。圓孔和長圓孔為2層。",
        "Rotates the bridges from the reference. Without a reference it only applies to round holes "
        "and manual layers, as other holes set their own directions.":
            "相對參考方向旋轉搭橋。沒有參考方向時，僅對圓孔和手動層數生效，其他孔由自身邊方向決定。",
        "Counterbore floor {} not found.": "找不到沉頭孔底面 {}。",
        "The reference must be a straight edge, sketch line or construction axis.":
            "參考方向必須是直邊、草圖直線或構造軸。",
        "The reference is perpendicular to the counterbore floor.": "參考方向垂直於沉頭孔底面。",
        "The counterbore floor must be planar and contain a hole.": "沉頭孔底面必須是平面且包含孔。",
        "Need at least one layer and a positive layer height.": "至少需要一層，且層高必須大於零。",
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
        "Optional: straight edge, sketch line or axis the first bridges run along, instead of the hole's edges.":
            "Optional: gerade Kante, Skizzenlinie oder Achse, entlang der die ersten Brücken verlaufen, "
            "statt entlang der Bohrungskanten.",
        "Angle": "Winkel",
        "Layer height": "Schichthöhe",
        "Layers": "Schichten",
        "Layers from hole shape": "Schichten aus Bohrungsform",
        "One layer per straight-edge direction of the hole, e.g. 3 for a hex hole. Round holes and slots get 2.":
            "Eine Schicht pro Richtung gerader Bohrungskanten, z. B. 3 bei einer Sechskantbohrung. "
            "Runde Bohrungen und Langlöcher erhalten 2.",
        "Rotates the bridges from the reference. Without a reference it only applies to round holes "
        "and manual layers, as other holes set their own directions.":
            "Dreht die Brücken gegenüber der Referenz. Ohne Referenz wirkt er nur bei runden Bohrungen und "
            "manueller Schichtanzahl, da andere Bohrungen ihre Richtungen selbst vorgeben.",
        "Counterbore floor {} not found.": "Senkungsboden {} nicht gefunden.",
        "The reference must be a straight edge, sketch line or construction axis.":
            "Die Referenz muss eine gerade Kante, Skizzenlinie oder Konstruktionsachse sein.",
        "The reference is perpendicular to the counterbore floor.": "Die Referenz steht senkrecht auf dem Senkungsboden.",
        "The counterbore floor must be planar and contain a hole.":
            "Der Senkungsboden muss eben sein und eine Bohrung enthalten.",
        "Need at least one layer and a positive layer height.":
            "Mindestens eine Schicht und eine positive Schichthöhe erforderlich.",
    },
}


def tr(text: str) -> str:
    language = adsk.core.Application.get().preferences.generalPreferences.userLanguage
    return _TRANSLATIONS.get(language, {}).get(text, text)
