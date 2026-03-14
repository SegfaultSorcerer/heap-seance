package com.example.leaks;

import java.util.HashMap;
import java.util.Map;

public final class LeakMapScenario {
    private static final Map<Integer, byte[]> LEAK = new HashMap<>();

    private LeakMapScenario() {
    }

    public static void main(String[] args) throws Exception {
        System.out.println("LeakMapScenario started");
        int i = 0;
        while (true) {
            LEAK.put(i, new byte[256 * 1024]);
            i++;
            if (i % 20 == 0) {
                long mb = ((long) i * 256L) / 1024L;
                System.out.printf("entries=%d approx_payload_mb=%d%n", i, mb);
            }
            Thread.sleep(200);
        }
    }
}
