"""앱 전용 예외.

모든 예외가 '원인(message)'과 '해결 힌트(hint)'를 함께 들고 다닌다.
decorators.handle_errors 가 이 예외를 잡아서 스택트레이스 대신
    [오류] 원인
    [힌트] 해결 방법
형태로 출력한다.
"""


class AppError(Exception):
    """사용자에게 그대로 보여줘도 되는 오류의 부모 클래스."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(AppError):
    """입력값 형식이 틀렸을 때 (날짜, 금액, type 등).

    대화형 입력에서는 이 예외가 나면 같은 질문을 다시 한다.
    """


class NotFoundError(AppError):
    """없는 거래 id, 카테고리, 파일 등을 찾으려 할 때."""
