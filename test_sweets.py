"""self-check: every dessert renders, can be eaten to crumbs, and every material has a colour."""
import models
import sweets

for theme, pal in sweets.THEMES.items():
    assert pal is None or set(pal) == set(models.MATS), f"{theme} is missing colours"
assert set(sweets.ANSI) == set(models.MATS)

for did in models.DESSERTS:
    table = sweets.Table(did, 100, 30)
    (rows, slots), _ = table.render(0.7, 0)
    assert set("".join(rows)) & set(sweets.RAMP), f"{did}: dessert drew nothing"
    assert not set(sweets.RAMP) & set(sweets.PLATE_RAMP), "dessert and plate must not share symbols"
    assert any(s // 2 != models.MAT["plate"] for s in slots if s != 255), f"{did}: no dessert material on screen"
    table.eat(0)
    (half, _), _ = table.render(0.7, 0, 0.5)
    assert 0 < len(table.eaten["pts"]) < len(table.model(0).pts), f"{did}: half eaten should leave some"
    (gone, _), _ = table.render(0.7, 0, 1.0)
    assert half != gone
    sweets.Table(did, 40, 12).render(0.0, 0)  # tiny terminal: clipped, must not crash
print("ok")
