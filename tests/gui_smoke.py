"""Run manually inside an isolated X11 desktop; never sends keys."""
import tempfile
from pathlib import Path
import tkinter as tk

import aion_healer.app as module
from aion_healer.app import App
from aion_healer.core import health_percent
from aion_healer.desktop import Desktop


def main():
    root = tk.Tk()
    app = App(root)
    bar = tk.Toplevel(root)
    bar.overrideredirect(True)
    bar.geometry("100x10+900+100")
    canvas = tk.Canvas(bar, width=100, height=10, highlightthickness=0, bg="#151515")
    canvas.pack()
    canvas.create_rectangle(0, 0, 25, 10, fill="#00c83c", outline="")
    failures = []

    def begin():
        try:
            image = Desktop().screenshot()
            assert health_percent(image.crop((900, 100, 1000, 110)), (0, 200, 60)) == 25
            app.rows[0][0].set(True)
            for field, value in zip(app.rows[0][1], ["Teste", "f1", "900,100,100,10", "00c83c"]):
                field.set(value)
            app.start()
            root.after(1800, finish)
        except Exception as exc:
            failures.append(exc)
            app.close()

    def finish():
        try:
            app.stop()
            app.worker.join(timeout=5)
            app.poll()
            text = app.log.get("1.0", "end")
            assert "SIMULAÇÃO: Teste 25.0% → f1, 1" in text, text
            original = module.CONFIG
            try:
                with tempfile.TemporaryDirectory() as temporary:
                    module.CONFIG = Path(temporary) / "config.json"
                    app.save()
                    assert module.CONFIG.exists()
                    app.rows[0][1][0].set("alterado")
                    app.load()
                    assert app.rows[0][1][0].get() == "Teste"
            finally:
                module.CONFIG = original
            print("PASS: GUI, X11 capture, 25% health, simulated heal, save/load, shutdown; no keys sent.")
        except Exception as exc:
            failures.append(exc)
        finally:
            app.close()

    root.after(500, begin)
    root.mainloop()
    if failures:
        raise failures[0]


if __name__ == "__main__":
    main()
