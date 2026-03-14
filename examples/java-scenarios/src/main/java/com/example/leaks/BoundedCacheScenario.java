package com.example.leaks;

import java.util.LinkedHashMap;
import java.util.Map;

public final class BoundedCacheScenario {
    private static final int MAX_ENTRIES = 512;

    private static final Map<Integer, byte[]> CACHE = new LinkedHashMap<>() {
        @Override
        protected boolean removeEldestEntry(Map.Entry<Integer, byte[]> eldest) {
            return size() > MAX_ENTRIES;
        }
    };

    private BoundedCacheScenario() {
    }

    public static void main(String[] args) throws Exception {
        System.out.println("BoundedCacheScenario started");
        int i = 0;
        while (true) {
            CACHE.put(i, new byte[256 * 1024]);
            i++;
            if (i % 50 == 0) {
                System.out.printf("writes=%d cache_size=%d%n", i, CACHE.size());
            }
            Thread.sleep(120);
        }
    }
}
