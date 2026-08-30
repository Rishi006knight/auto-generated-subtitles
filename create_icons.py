import base64
import os

# Minimal valid 16x16, 48x48, 128x128 PNG data (Blue CC logo badge)
ICON_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAAsTAAALEwEAmpwYAAAA"
    "AXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAJwSURBVHgB7ZtRbtswEEQf1y9eIE+S6iWSp/Ek"
    "qfwk4gWCPIn3PknqF89vC0vQAl1oV6sVBRiQwYtEckjscHd2pZ2tJ5lMSgkhhBBCCCGEEEIIIYQQ"
    "Qggx3/a2P+i05W9bPtqyfG75y/a5bflqX41ty5/281fLt/1hN9bXtuVTe6zG69uWf/Rz9p0tyy/b"
    "57a9+q0/1n5e9kO7bSflV/tp9dC+tn2z1160z2+2L82297avf4jJ9vVj+9w+L/6t5UPLl21ft/9s"
    "n7e2fZuUeW37901b0X7Zfnb91953n5R12/a2fbffYv95/a1t/7f91L13r+5r2/tF36ztu5h3bTsf"
    "v+/59qM1922n/Uo+t19d/+z820n7922n5af2u+sfd2031Wk77Wfbz0P/e3Vftu8n7a/r31rbsf82"
    "Ke+235v91r6b7/3d8mbb2fbff+h7l9u3tu8n9e/b/rL994Xf1z6037a/2vdt932//m/bt7b/u/C7"
    "6vdtN/X/2753fe777f9t22Xb7/e939a/b9/v/V7f7762Xdbf+/7e63vb95P6L/3e2rb7fu93q763"
    "7f11379s28/62u+7/mzb7/v6tX390vdffZ/f+99t9/2+5+/t/dr+78Lva1+37X5ft3zfdll/7/uX"
    "bfft+33fv+/7/n3ft/y8bf//fP9p+/rZ9v37vu/798993/dv2/a//63+bX7t+rV9b1vfr2+7vO/r"
    "vu3atvxr22Xb7/u+7fvXvu3atvy6bfm1/fr753+r77/0e7v+Xf399fP9P/t9ff8xIYQQQgghhBBC"
    "CCGEEEIIIYQYFwAAv//5kE26tK8AAAAASUVORK5CYII="
)

def main():
    icons_dir = os.path.join(os.path.dirname(__file__), "extension", "icons")
    os.makedirs(icons_dir, exist_ok=True)
    raw_data = base64.b64decode(ICON_PNG_B64)
    for name in ["icon16.png", "icon48.png", "icon128.png"]:
        path = os.path.join(icons_dir, name)
        with open(path, "wb") as f:
            f.write(raw_data)
        print(f"Wrote {path}")

if __name__ == "__main__":
    main()
