try:
    import pytest
    import tests.integration.test_nodes
    print("SUCCESS")
except Exception as e:
    import traceback
    open('trace.txt', 'w', encoding='utf-8').write(traceback.format_exc())
