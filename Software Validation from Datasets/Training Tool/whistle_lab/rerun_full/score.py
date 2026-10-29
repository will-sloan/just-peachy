"""Sequential, resumable native WER scoring using the unchanged decoder."""
import traceback
from runtime import *
if __name__ == "__main__":
    try:
        raise SystemExit(shared("score").main())
    except Exception as error:
        status("failed", message=str(error), traceback=traceback.format_exc())
        raise
