"""`python -m budget_app` 으로 실행하면 파이썬이 이 파일을 실행한다.

main() 이 돌려준 숫자가 프로그램의 종료 코드가 된다. (0 = 정상, 그 외 = 오류)
"""

import sys

from budget_app.cli import main

if __name__ == "__main__":
    sys.exit(main())
