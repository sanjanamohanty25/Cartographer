# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

import sys
import asyncio

# asyncio.timeout context manager was introduced in Python 3.11.
# For Python 3.10 and below, we monkey-patch it using the async_timeout library.
if sys.version_info < (3, 11):
    try:
        import async_timeout
        asyncio.timeout = async_timeout.timeout
    except ImportError:
        # Fallback empty context manager in case async_timeout is not available
        import contextlib
        @contextlib.asynccontextmanager
        async def fallback_timeout(delay):
            yield
        asyncio.timeout = fallback_timeout
