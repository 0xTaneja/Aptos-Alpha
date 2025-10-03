/// Trading Engine Module for Aptos Alpha Bot
/// Handles order placement, execution, and strategy management
module aptos_alpha_bot::trading_engine {
    use std::signer;
    use std::vector;
    use std::error;
    use std::option::{Self, Option};
    use std::string::{Self, String};
    use aptos_framework::timestamp;
    use aptos_framework::event::{Self, EventHandle};
    use aptos_framework::account;
    use aptos_framework::table::{Self, Table};

    /// Error codes
    const E_NOT_AUTHORIZED: u64 = 1;
    const E_INSUFFICIENT_BALANCE: u64 = 2;
    const E_ORDER_NOT_FOUND: u64 = 3;
    const E_INVALID_PRICE: u64 = 4;
    const E_INVALID_AMOUNT: u64 = 5;
    const E_STRATEGY_NOT_FOUND: u64 = 6;

    /// Order sides
    const ORDER_SIDE_BUY: u8 = 1;
    const ORDER_SIDE_SELL: u8 = 2;

    /// Order status
    const ORDER_STATUS_PENDING: u8 = 1;
    const ORDER_STATUS_FILLED: u8 = 2;
    const ORDER_STATUS_CANCELLED: u8 = 3;

    /// Strategy types
    const STRATEGY_GRID: u8 = 1;
    const STRATEGY_MOMENTUM: u8 = 2;
    const STRATEGY_ARBITRAGE: u8 = 3;

    /// Order structure
    struct Order has store, drop {
        id: u64,
        user: address,
        symbol: String,
        side: u8,
        amount: u64,
        price: u64,
        status: u8,
        created_at: u64,
        filled_at: Option<u64>,
        strategy_id: Option<u64>,
    }

    /// Grid trading strategy parameters
    struct GridStrategy has store, drop {
        id: u64,
        user: address,
        symbol: String,
        base_price: u64,
        grid_spacing: u64, // in basis points (100 = 1%)
        num_levels: u8,
        amount_per_level: u64,
        active: bool,
        created_at: u64,
    }

    /// Trading engine resource
    struct TradingEngine has key {
        /// Order management
        orders: Table<u64, Order>,
        next_order_id: u64,
        user_orders: Table<address, vector<u64>>,
        
        /// Strategy management
        strategies: Table<u64, GridStrategy>,
        next_strategy_id: u64,
        user_strategies: Table<address, vector<u64>>,
        
        /// Market data (simplified for demo)
        market_prices: Table<String, u64>,
        
        /// Events
        order_events: EventHandle<OrderEvent>,
        fill_events: EventHandle<FillEvent>,
        strategy_events: EventHandle<StrategyEvent>,
    }

    /// Events
    struct OrderEvent has drop, store {
        order_id: u64,
        user: address,
        symbol: String,
        side: u8,
        amount: u64,
        price: u64,
        timestamp: u64,
    }

    struct FillEvent has drop, store {
        order_id: u64,
        user: address,
        symbol: String,
        side: u8,
        amount: u64,
        price: u64,
        timestamp: u64,
    }

    struct StrategyEvent has drop, store {
        strategy_id: u64,
        user: address,
        strategy_type: u8,
        symbol: String,
        active: bool,
        timestamp: u64,
    }

    /// Initialize the trading engine
    public entry fun initialize_engine(admin: &signer) acquires TradingEngine {
        let admin_addr = signer::address_of(admin);
        
        assert!(!exists<TradingEngine>(admin_addr), error::already_exists(E_ORDER_NOT_FOUND));
        
        let engine = TradingEngine {
            orders: table::new<u64, Order>(),
            next_order_id: 1,
            user_orders: table::new<address, vector<u64>>(),
            strategies: table::new<u64, GridStrategy>(),
            next_strategy_id: 1,
            user_strategies: table::new<address, vector<u64>>(),
            market_prices: table::new<String, u64>(),
            order_events: account::new_event_handle<OrderEvent>(admin),
            fill_events: account::new_event_handle<FillEvent>(admin),
            strategy_events: account::new_event_handle<StrategyEvent>(admin),
        };
        
        move_to(admin, engine);
        
        // Initialize some demo market prices
        update_market_price(admin, string::utf8(b"APT/USDC"), 1000000); // $10.00
        update_market_price(admin, string::utf8(b"BTC/USDC"), 6500000000); // $65,000.00
        update_market_price(admin, string::utf8(b"ETH/USDC"), 300000000); // $3,000.00
    }

    /// Place a limit order
    public entry fun place_order(
        user: &signer,
        engine_owner: address,
        symbol: vector<u8>,
        side: u8,
        amount: u64,
        price: u64,
    ) acquires TradingEngine {
        let user_addr = signer::address_of(user);
        
        assert!(exists<TradingEngine>(engine_owner), error::not_found(E_ORDER_NOT_FOUND));
        assert!(side == ORDER_SIDE_BUY || side == ORDER_SIDE_SELL, error::invalid_argument(E_INVALID_PRICE));
        assert!(amount > 0, error::invalid_argument(E_INVALID_AMOUNT));
        assert!(price > 0, error::invalid_argument(E_INVALID_PRICE));
        
        let engine = borrow_global_mut<TradingEngine>(engine_owner);
        let symbol_str = string::utf8(symbol);
        
        // Create new order
        let order = Order {
            id: engine.next_order_id,
            user: user_addr,
            symbol: symbol_str,
            side,
            amount,
            price,
            status: ORDER_STATUS_PENDING,
            created_at: timestamp::now_seconds(),
            filled_at: option::none<u64>(),
            strategy_id: option::none<u64>(),
        };
        
        // Store order
        table::add(&mut engine.orders, engine.next_order_id, order);
        
        // Update user orders
        if (!table::contains(&engine.user_orders, user_addr)) {
            table::add(&mut engine.user_orders, user_addr, vector::empty<u64>());
        };
        let user_order_list = table::borrow_mut(&mut engine.user_orders, user_addr);
        vector::push_back(user_order_list, engine.next_order_id);
        
        // Emit order event
        event::emit_event(&mut engine.order_events, OrderEvent {
            order_id: engine.next_order_id,
            user: user_addr,
            symbol: symbol_str,
            side,
            amount,
            price,
            timestamp: timestamp::now_seconds(),
        });
        
        let order_id = engine.next_order_id;
        engine.next_order_id = engine.next_order_id + 1;
        
        // Try to fill order immediately (simplified matching)
        try_fill_order(engine, order_id);
    }

    /// Cancel an order
    public entry fun cancel_order(
        user: &signer,
        engine_owner: address,
        order_id: u64,
    ) acquires TradingEngine {
        let user_addr = signer::address_of(user);
        
        assert!(exists<TradingEngine>(engine_owner), error::not_found(E_ORDER_NOT_FOUND));
        
        let engine = borrow_global_mut<TradingEngine>(engine_owner);
        
        assert!(table::contains(&engine.orders, order_id), error::not_found(E_ORDER_NOT_FOUND));
        
        let order = table::borrow_mut(&mut engine.orders, order_id);
        assert!(order.user == user_addr, error::permission_denied(E_NOT_AUTHORIZED));
        assert!(order.status == ORDER_STATUS_PENDING, error::invalid_state(E_ORDER_NOT_FOUND));
        
        order.status = ORDER_STATUS_CANCELLED;
    }

    /// Create a grid trading strategy
    public entry fun create_grid_strategy(
        user: &signer,
        engine_owner: address,
        symbol: vector<u8>,
        base_price: u64,
        grid_spacing: u64,
        num_levels: u8,
        amount_per_level: u64,
    ) acquires TradingEngine {
        let user_addr = signer::address_of(user);
        
        assert!(exists<TradingEngine>(engine_owner), error::not_found(E_STRATEGY_NOT_FOUND));
        assert!(num_levels > 0 && num_levels <= 20, error::invalid_argument(E_INVALID_AMOUNT));
        assert!(grid_spacing > 0 && grid_spacing <= 1000, error::invalid_argument(E_INVALID_PRICE)); // Max 10%
        
        let engine = borrow_global_mut<TradingEngine>(engine_owner);
        let symbol_str = string::utf8(symbol);
        
        // Create grid strategy
        let strategy = GridStrategy {
            id: engine.next_strategy_id,
            user: user_addr,
            symbol: symbol_str,
            base_price,
            grid_spacing,
            num_levels,
            amount_per_level,
            active: true,
            created_at: timestamp::now_seconds(),
        };
        
        // Store strategy
        table::add(&mut engine.strategies, engine.next_strategy_id, strategy);
        
        // Update user strategies
        if (!table::contains(&engine.user_strategies, user_addr)) {
            table::add(&mut engine.user_strategies, user_addr, vector::empty<u64>());
        };
        let user_strategy_list = table::borrow_mut(&mut engine.user_strategies, user_addr);
        vector::push_back(user_strategy_list, engine.next_strategy_id);
        
        // Emit strategy event
        event::emit_event(&mut engine.strategy_events, StrategyEvent {
            strategy_id: engine.next_strategy_id,
            user: user_addr,
            strategy_type: STRATEGY_GRID,
            symbol: symbol_str,
            active: true,
            timestamp: timestamp::now_seconds(),
        });
        
        let strategy_id = engine.next_strategy_id;
        engine.next_strategy_id = engine.next_strategy_id + 1;
        
        // Place initial grid orders
        place_grid_orders(engine, strategy_id, user_addr);
    }

    /// Update market price (admin only)
    public entry fun update_market_price(
        admin: &signer,
        symbol: String,
        price: u64,
    ) acquires TradingEngine {
        let admin_addr = signer::address_of(admin);
        
        assert!(exists<TradingEngine>(admin_addr), error::not_found(E_ORDER_NOT_FOUND));
        
        let engine = borrow_global_mut<TradingEngine>(admin_addr);
        
        if (table::contains(&engine.market_prices, symbol)) {
            let current_price = table::borrow_mut(&mut engine.market_prices, symbol);
            *current_price = price;
        } else {
            table::add(&mut engine.market_prices, symbol, price);
        };
    }

    /// Get market price
    public fun get_market_price(engine_owner: address, symbol: String): u64 acquires TradingEngine {
        assert!(exists<TradingEngine>(engine_owner), error::not_found(E_ORDER_NOT_FOUND));
        
        let engine = borrow_global<TradingEngine>(engine_owner);
        
        if (table::contains(&engine.market_prices, symbol)) {
            *table::borrow(&engine.market_prices, symbol)
        } else {
            0
        }
    }

    /// Get user orders
    public fun get_user_orders(engine_owner: address, user_addr: address): vector<u64> acquires TradingEngine {
        assert!(exists<TradingEngine>(engine_owner), error::not_found(E_ORDER_NOT_FOUND));
        
        let engine = borrow_global<TradingEngine>(engine_owner);
        
        if (table::contains(&engine.user_orders, user_addr)) {
            *table::borrow(&engine.user_orders, user_addr)
        } else {
            vector::empty<u64>()
        }
    }

    /// Helper function to try filling an order
    fun try_fill_order(engine: &mut TradingEngine, order_id: u64) {
        if (!table::contains(&engine.orders, order_id)) {
            return
        };
        
        let order = table::borrow_mut(&mut engine.orders, order_id);
        if (order.status != ORDER_STATUS_PENDING) {
            return
        };
        
        // Get current market price
        let market_price = if (table::contains(&engine.market_prices, order.symbol)) {
            *table::borrow(&engine.market_prices, order.symbol)
        } else {
            return
        };
        
        // Simple fill logic: fill if price is favorable
        let should_fill = if (order.side == ORDER_SIDE_BUY) {
            market_price <= order.price
        } else {
            market_price >= order.price
        };
        
        if (should_fill) {
            order.status = ORDER_STATUS_FILLED;
            order.filled_at = option::some(timestamp::now_seconds());
            
            // Emit fill event
            event::emit_event(&mut engine.fill_events, FillEvent {
                order_id: order.id,
                user: order.user,
                symbol: order.symbol,
                side: order.side,
                amount: order.amount,
                price: market_price,
                timestamp: timestamp::now_seconds(),
            });
        };
    }

    /// Helper function to place grid orders
    fun place_grid_orders(engine: &mut TradingEngine, strategy_id: u64, user_addr: address) {
        if (!table::contains(&engine.strategies, strategy_id)) {
            return
        };
        
        let strategy = table::borrow(&engine.strategies, strategy_id);
        if (!strategy.active) {
            return
        };
        
        let base_price = strategy.base_price;
        let grid_spacing = strategy.grid_spacing;
        let num_levels = strategy.num_levels;
        let amount_per_level = strategy.amount_per_level;
        
        // Place buy orders below base price
        let i = 1;
        while (i <= num_levels / 2) {
            let price_offset = (base_price * grid_spacing * (i as u64)) / 10000;
            let buy_price = base_price - price_offset;
            
            let buy_order = Order {
                id: engine.next_order_id,
                user: user_addr,
                symbol: strategy.symbol,
                side: ORDER_SIDE_BUY,
                amount: amount_per_level,
                price: buy_price,
                status: ORDER_STATUS_PENDING,
                created_at: timestamp::now_seconds(),
                filled_at: option::none<u64>(),
                strategy_id: option::some(strategy_id),
            };
            
            table::add(&mut engine.orders, engine.next_order_id, buy_order);
            engine.next_order_id = engine.next_order_id + 1;
            
            i = i + 1;
        };
        
        // Place sell orders above base price
        i = 1;
        while (i <= num_levels / 2) {
            let price_offset = (base_price * grid_spacing * (i as u64)) / 10000;
            let sell_price = base_price + price_offset;
            
            let sell_order = Order {
                id: engine.next_order_id,
                user: user_addr,
                symbol: strategy.symbol,
                side: ORDER_SIDE_SELL,
                amount: amount_per_level,
                price: sell_price,
                status: ORDER_STATUS_PENDING,
                created_at: timestamp::now_seconds(),
                filled_at: option::none<u64>(),
                strategy_id: option::some(strategy_id),
            };
            
            table::add(&mut engine.orders, engine.next_order_id, sell_order);
            engine.next_order_id = engine.next_order_id + 1;
            
            i = i + 1;
        };
    }

    #[test_only]
    use aptos_framework::account::create_account_for_test;

    #[test(admin = @aptos_alpha_bot, user = @0x123)]
    public entry fun test_trading_engine(admin: signer, user: signer) acquires TradingEngine {
        let admin_addr = signer::address_of(&admin);
        let user_addr = signer::address_of(&user);
        
        // Create accounts for testing
        create_account_for_test(admin_addr);
        create_account_for_test(user_addr);
        
        // Initialize engine
        initialize_engine(&admin);
        
        // Test placing an order
        place_order(&user, admin_addr, b"APT/USDC", ORDER_SIDE_BUY, 1000000, 950000);
        
        // Verify order was placed
        let user_orders = get_user_orders(admin_addr, user_addr);
        assert!(vector::length(&user_orders) == 1, 1);
        
        // Test market price
        let price = get_market_price(admin_addr, string::utf8(b"APT/USDC"));
        assert!(price == 1000000, 2);
    }
}
